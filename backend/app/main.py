from __future__ import annotations

import base64
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import AnyUrl, BaseModel, ConfigDict, EmailStr, Field, field_validator
from pwdlib import PasswordHash
from sqlmodel import Field as DBField, Session, SQLModel, create_engine, select

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./biashara.db")
# Render provides PostgreSQL URLs with the legacy ``postgres://`` scheme;
# SQLAlchemy 2 requires the explicit psycopg driver for PostgreSQL.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL.removeprefix("postgres://")
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL.removeprefix("postgresql://")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
password_hash = PasswordHash.recommended()
JWT_SECRET = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET or len(JWT_SECRET) < 32:
    raise RuntimeError("Set JWT_SECRET_KEY to a random value of at least 32 characters")
JWT_ALGORITHM = "HS256"
TOKEN_TTL = int(os.getenv("JWT_EXPIRES_MINUTES", "60")) * 60
DARAJA_TIMEOUT = max(1, int(os.getenv("DARAJA_TIMEOUT_SECONDS", "20")))


def now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: Optional[int] = DBField(default=None, primary_key=True)
    name: str
    email: str = DBField(index=True, unique=True)
    password_hash: str
    role: str
    created_at: datetime = DBField(default_factory=now)


class Vendor(SQLModel, table=True):
    id: Optional[int] = DBField(default=None, primary_key=True)
    user_id: int = DBField(foreign_key="user.id", unique=True)
    business_name: str
    phone: str
    county: str
    description: Optional[str] = None
    status: str = "pending"
    review_note: Optional[str] = None
    created_at: datetime = DBField(default_factory=now)


class Product(SQLModel, table=True):
    id: Optional[int] = DBField(default=None, primary_key=True)
    vendor_id: int = DBField(foreign_key="vendor.id", index=True)
    name: str
    description: str
    price_kes: int
    stock: int
    category: str = DBField(index=True)
    image_url: Optional[str] = None
    created_at: datetime = DBField(default_factory=now)


class CartLine(SQLModel, table=True):
    id: Optional[int] = DBField(default=None, primary_key=True)
    customer_id: int = DBField(foreign_key="user.id", index=True)
    product_id: int = DBField(foreign_key="product.id")
    quantity: int


class Order(SQLModel, table=True):
    id: Optional[int] = DBField(default=None, primary_key=True)
    customer_id: int = DBField(foreign_key="user.id", index=True)
    vendor_id: int = DBField(foreign_key="vendor.id", index=True)
    items_json: str
    total_kes: int
    status: str = "pending_payment"
    delivery_address: str
    delivery_phone: Optional[str] = None
    delivery_status: str = "not_dispatched"
    tracking_reference: Optional[str] = None
    delivery_note: Optional[str] = None
    created_at: datetime = DBField(default_factory=now)
    updated_at: datetime = DBField(default_factory=now)


class Payment(SQLModel, table=True):
    id: Optional[int] = DBField(default=None, primary_key=True)
    order_id: int = DBField(foreign_key="order.id", index=True)
    amount_kes: int
    status: str = "pending"
    provider: str = "mpesa_daraja_sandbox"
    checkout_request_id: Optional[str] = DBField(default=None, unique=True)
    merchant_request_id: Optional[str] = None
    receipt_number: Optional[str] = None
    result_code: Optional[int] = None
    callback_payload: Optional[str] = None
    created_at: datetime = DBField(default_factory=now)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Register(Strict):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: str
    @field_validator("role")
    @classmethod
    def user_role(cls, v):
        if v not in ("customer", "vendor"): raise ValueError("role must be customer or vendor")
        return v

class Login(Strict):
    email: EmailStr
    password: str = Field(min_length=1)

class VendorIn(Strict):
    business_name: str = Field(min_length=2, max_length=160)
    phone: str
    county: str = Field(min_length=2, max_length=80)
    description: Optional[str] = Field(default=None, max_length=2000)
    @field_validator("phone")
    @classmethod
    def kenyan_phone(cls, v):
        if len(v) != 13 or not v.startswith("+254") or v[4] not in "17" or not v[5:].isdigit(): raise ValueError("phone must match +254[17]XXXXXXXX")
        return v

class ProductIn(Strict):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(max_length=5000)
    price_kes: int = Field(ge=1, le=100000000)
    stock: int = Field(ge=0, le=1000000)
    category: str = Field(min_length=1, max_length=80)
    image_url: Optional[AnyUrl] = Field(default=None, max_length=2048)

class ProductPatch(Strict):
    name: Optional[str] = Field(default=None, min_length=2, max_length=160)
    description: Optional[str] = Field(default=None, max_length=5000)
    price_kes: Optional[int] = Field(default=None, ge=1, le=100000000)
    stock: Optional[int] = Field(default=None, ge=0, le=1000000)
    category: Optional[str] = Field(default=None, min_length=1, max_length=80)
    image_url: Optional[AnyUrl] = Field(default=None, max_length=2048)

class CartIn(Strict):
    items: list[dict[str, Any]] = Field(max_length=100)

class CreateOrder(Strict):
    delivery_address: str = Field(min_length=5, max_length=1000)
    delivery_phone: Optional[str] = None

class StkIn(Strict):
    order_id: int = Field(ge=1)
    phone: str

class Approval(Strict):
    status: str
    review_note: Optional[str] = Field(default=None, max_length=1000)
    @field_validator("status")
    @classmethod
    def approval_status(cls, v):
        if v not in ("approved", "rejected"): raise ValueError("status must be approved or rejected")
        return v

class DeliveryIn(Strict):
    status: str
    tracking_reference: Optional[str] = Field(default=None, max_length=120)
    note: Optional[str] = Field(default=None, max_length=1000)
    @field_validator("status")
    @classmethod
    def delivery_status_value(cls, v):
        if v not in ("not_dispatched", "processing", "shipped", "delivered"): raise ValueError("invalid delivery status")
        return v


def get_session():
    with Session(engine) as session: yield session


def error(status: int, code: str, message: str, details: dict | None = None):
    raise HTTPException(status, {"code": code, "message": message, "details": details or {}})


def user_out(u: User):
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "created_at": u.created_at}

def vendor_out(v: Vendor):
    return {"id": v.id, "user_id": v.user_id, "business_name": v.business_name, "phone": v.phone, "county": v.county, "description": v.description, "status": v.status, "created_at": v.created_at}

def product_out(p: Product):
    return {"id": p.id, "vendor_id": p.vendor_id, "name": p.name, "description": p.description, "price_kes": p.price_kes, "stock": p.stock, "category": p.category, "image_url": p.image_url, "created_at": p.created_at}

def order_out(o: Order):
    import json
    result = {"id": o.id, "customer_id": o.customer_id, "vendor_id": o.vendor_id, "items": json.loads(o.items_json), "total_kes": o.total_kes, "status": o.status, "delivery_address": o.delivery_address, "delivery_phone": o.delivery_phone, "delivery_status": o.delivery_status, "created_at": o.created_at, "updated_at": o.updated_at}
    return result

def payment_out(p: Payment):
    return {"id": p.id, "order_id": p.order_id, "amount_kes": p.amount_kes, "status": p.status, "provider": p.provider, "checkout_request_id": p.checkout_request_id, "receipt_number": p.receipt_number, "result_code": p.result_code, "created_at": p.created_at}


def current_user(authorization: str | None = Header(default=None), session: Session = Depends(get_session)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "): error(401, "unauthorized", "Authentication required")
    try:
        data = jwt.decode(authorization.split(None, 1)[1], JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = session.get(User, int(data["sub"]))
    except Exception: user = None
    if not user: error(401, "unauthorized", "Invalid or expired token")
    return user

def require_role(user: User, *roles):
    if user.role not in roles: error(403, "forbidden", "Insufficient permissions")

def owned_order(session: Session, order_id: int, user: User):
    o = session.get(Order, order_id)
    if not o: error(404, "not_found", "Order not found")
    if user.role == "admin": return o
    if user.role == "customer" and o.customer_id == user.id: return o
    if user.role == "vendor":
        v = session.exec(select(Vendor).where(Vendor.user_id == user.id)).first()
        if v and v.id == o.vendor_id: return o
    error(403, "forbidden", "Order is not accessible")

def token_for(user: User):
    expiry = now() + timedelta(seconds=TOKEN_TTL)
    return {"access_token": jwt.encode({"sub": str(user.id), "exp": expiry}, JWT_SECRET, algorithm=JWT_ALGORITHM), "token_type": "bearer", "expires_in": TOKEN_TTL, "user": user_out(user)}

app = FastAPI(title="Biashara Hub API", version="1.0.0")
origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"] , allow_headers=["Authorization", "Content-Type"])

@app.exception_handler(HTTPException)
async def http_error_handler(request, exc):
    if isinstance(exc.detail, dict) and "code" in exc.detail: return Response(content=__import__('json').dumps(exc.detail), status_code=exc.status_code, media_type="application/json")
    return Response(content=__import__('json').dumps({"code": {401:"unauthorized",403:"forbidden",404:"not_found",409:"conflict",502:"upstream_error"}.get(exc.status_code,"validation_error"), "message": str(exc.detail), "details": {}}), status_code=exc.status_code, media_type="application/json")

@app.exception_handler(422)
async def validation_error_handler(request, exc):
    from fastapi.exceptions import RequestValidationError
    details = {"errors": exc.errors()} if isinstance(exc, RequestValidationError) else {}
    return Response(content=__import__('json').dumps({"code":"validation_error","message":"Request validation failed","details":details}, default=str), status_code=422, media_type="application/json")

@app.on_event("startup")
def startup():
    SQLModel.metadata.create_all(engine)
    admin_email = os.getenv("INITIAL_ADMIN_EMAIL", "").strip().lower()
    admin_password = os.getenv("INITIAL_ADMIN_PASSWORD", "")
    if bool(admin_email) != bool(admin_password):
        raise RuntimeError("Set both INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD to bootstrap an admin")
    if not admin_email:
        return
    if len(admin_password) < 12:
        raise RuntimeError("INITIAL_ADMIN_PASSWORD must be at least 12 characters")
    with Session(engine) as session:
        existing = session.exec(select(User).where(User.email == admin_email)).first()
        if existing:
            if existing.role != "admin":
                raise RuntimeError("INITIAL_ADMIN_EMAIL is already registered without the admin role")
            return
        session.add(User(name="Initial Admin", email=admin_email, password_hash=password_hash.hash(admin_password), role="admin"))
        session.commit()

@app.get("/health")
def health(): return {"status":"ok", "version":"1.0.0"}

@app.get("/", include_in_schema=False)
def home(): return RedirectResponse(url="/docs")

@app.post("/auth/register", status_code=201)
def register(body: Register, session: Session = Depends(get_session)):
    email = str(body.email).lower()
    if session.exec(select(User).where(User.email == email)).first(): error(409,"conflict","Email already registered")
    u=User(name=body.name,email=email,password_hash=password_hash.hash(body.password),role=body.role); session.add(u); session.commit(); session.refresh(u); return user_out(u)

@app.post("/auth/login")
def login(body: Login, session: Session=Depends(get_session)):
    u=session.exec(select(User).where(User.email == str(body.email).lower())).first()
    if not u or not password_hash.verify(body.password,u.password_hash): error(401,"unauthorized","Invalid email or password")
    return token_for(u)

@app.get("/vendors/me")
def get_vendor(user: User=Depends(current_user),session: Session=Depends(get_session)):
    require_role(user,"vendor"); v=session.exec(select(Vendor).where(Vendor.user_id==user.id)).first()
    if not v: error(404,"not_found","Vendor profile not found")
    return vendor_out(v)

@app.put("/vendors/me")
def put_vendor(body: VendorIn,user: User=Depends(current_user),session: Session=Depends(get_session)):
    require_role(user,"vendor"); v=session.exec(select(Vendor).where(Vendor.user_id==user.id)).first()
    if not v: v=Vendor(user_id=user.id,**body.model_dump())
    else:
        for k,val in body.model_dump().items(): setattr(v,k,val)
        v.status="pending"; v.review_note=None
    session.add(v); session.commit(); session.refresh(v); return vendor_out(v)

@app.get("/admin/vendors")
def pending_vendors(status: str="pending",user: User=Depends(current_user),session: Session=Depends(get_session)):
    require_role(user,"admin")
    if status not in ("pending","approved","rejected"): error(422,"validation_error","Invalid vendor status")
    return [vendor_out(v) for v in session.exec(select(Vendor).where(Vendor.status==status)).all()]

@app.put("/admin/vendors/{vendor_id}/approval")
def review_vendor(vendor_id:int,body:Approval,user:User=Depends(current_user),session:Session=Depends(get_session)):
    require_role(user,"admin"); v=session.get(Vendor,vendor_id)
    if not v: error(404,"not_found","Vendor not found")
    v.status=body.status; v.review_note=body.review_note; session.add(v); session.commit(); session.refresh(v); return vendor_out(v)

def approved_vendor(session,user):
    require_role(user,"vendor"); v=session.exec(select(Vendor).where(Vendor.user_id==user.id)).first()
    if not v or v.status!="approved": error(403,"forbidden","Approved vendor profile required")
    return v

@app.get("/products")
def list_products(q:Optional[str]=Query(default=None,max_length=120),category:Optional[str]=Query(default=None,max_length=80),page:int=Query(default=1,ge=1),page_size:int=Query(default=20,ge=1,le=100),session:Session=Depends(get_session)):
    stmt=select(Product).join(Vendor,Product.vendor_id==Vendor.id).where(Vendor.status=="approved")
    if q: stmt=stmt.where(Product.name.contains(q) | Product.description.contains(q))
    if category: stmt=stmt.where(Product.category==category)
    rows=session.exec(stmt).all(); return {"items":[product_out(p) for p in rows[(page-1)*page_size:page*page_size]],"page":page,"page_size":page_size,"total":len(rows)}

@app.post("/products",status_code=201)
def create_product(body:ProductIn,user:User=Depends(current_user),session:Session=Depends(get_session)):
    v=approved_vendor(session,user); p=Product(vendor_id=v.id,**body.model_dump(mode="json")); session.add(p); session.commit(); session.refresh(p); return product_out(p)

@app.get("/products/{product_id}")
def get_product(product_id:int,session:Session=Depends(get_session)):
    p=session.get(Product,product_id)
    if not p or not session.get(Vendor,p.vendor_id) or session.get(Vendor,p.vendor_id).status!="approved": error(404,"not_found","Product not found")
    return product_out(p)

@app.patch("/products/{product_id}")
def patch_product(product_id:int,body:ProductPatch,user:User=Depends(current_user),session:Session=Depends(get_session)):
    p=session.get(Product,product_id)
    if not p: error(404,"not_found","Product not found")
    v=approved_vendor(session,user)
    if p.vendor_id!=v.id: error(403,"forbidden","Product is not owned by vendor")
    values=body.model_dump(exclude_unset=True,mode="json")
    if not values: error(422,"validation_error","At least one field is required")
    for k,val in values.items(): setattr(p,k,val)
    session.add(p); session.commit(); session.refresh(p); return product_out(p)

@app.delete("/products/{product_id}",status_code=204)
def delete_product(product_id:int,user:User=Depends(current_user),session:Session=Depends(get_session)):
    p=session.get(Product,product_id)
    if not p: error(404,"not_found","Product not found")
    v=approved_vendor(session,user)
    if p.vendor_id!=v.id: error(403,"forbidden","Product is not owned by vendor")
    session.delete(p); session.commit(); return Response(status_code=204)

@app.get("/cart")
def get_cart(user:User=Depends(current_user),session:Session=Depends(get_session)):
    require_role(user,"customer"); lines=session.exec(select(CartLine).where(CartLine.customer_id==user.id)).all(); items=[]; total=0
    for l in lines:
        p=session.get(Product,l.product_id)
        if p:
            line=p.price_kes*l.quantity; total+=line; items.append({"product":product_out(p),"quantity":l.quantity,"line_total_kes":line})
    return {"items":items,"total_kes":total}

@app.put("/cart")
def set_cart(body:CartIn,user:User=Depends(current_user),session:Session=Depends(get_session)):
    require_role(user,"customer"); clean={}
    for x in body.items:
        if set(x)!={"product_id","quantity"} or not isinstance(x.get("product_id"),int) or not isinstance(x.get("quantity"),int) or x["product_id"]<1 or not 1<=x["quantity"]<=1000: error(422,"validation_error","Each cart item needs positive product_id and quantity 1..1000")
        clean[x["product_id"]]=clean.get(x["product_id"],0)+x["quantity"]
    for old in session.exec(select(CartLine).where(CartLine.customer_id==user.id)).all(): session.delete(old)
    for pid,qty in clean.items():
        p=session.get(Product,pid); v=session.get(Vendor,p.vendor_id) if p else None
        if not p or not v or v.status!="approved": error(422,"validation_error","Cart contains unavailable product")
        if qty>p.stock: error(409,"conflict","Cart quantity exceeds available stock")
        session.add(CartLine(customer_id=user.id,product_id=pid,quantity=qty))
    session.commit(); return get_cart(user,session)

@app.post("/orders",status_code=201)
def create_order(body:CreateOrder,user:User=Depends(current_user),session:Session=Depends(get_session)):
    require_role(user,"customer"); lines=session.exec(select(CartLine).where(CartLine.customer_id==user.id)).all()
    if not lines: error(409,"conflict","Cart is empty")
    items=[]; total=0; vendor_ids=set()
    for l in lines:
        p=session.get(Product,l.product_id); v=session.get(Vendor,p.vendor_id) if p else None
        if not p or not v or v.status!="approved" or p.stock<l.quantity: error(409,"conflict","Cart item unavailable or stock changed")
        vendor_ids.add(v.id); line=p.price_kes*l.quantity; total+=line
        items.append({"product_id":p.id,"product_name":p.name,"quantity":l.quantity,"unit_price_kes":p.price_kes,"line_total_kes":line})
    if len(vendor_ids)>1: error(409,"conflict","Cart items must belong to one vendor")
    o=Order(customer_id=user.id,vendor_id=next(iter(vendor_ids)),items_json=__import__('json').dumps(items),total_kes=total,delivery_address=body.delivery_address,delivery_phone=body.delivery_phone)
    for l in lines:
        p=session.get(Product,l.product_id); p.stock-=l.quantity; session.add(p); session.delete(l)
    session.add(o); session.commit(); session.refresh(o); return order_out(o)

@app.get("/orders")
def list_orders(status:Optional[str]=None,page:int=Query(default=1,ge=1),user:User=Depends(current_user),session:Session=Depends(get_session)):
    stmt=select(Order)
    if user.role=="customer": stmt=stmt.where(Order.customer_id==user.id)
    elif user.role=="vendor":
        v=session.exec(select(Vendor).where(Vendor.user_id==user.id)).first()
        stmt=stmt.where(Order.vendor_id==(v.id if v else -1))
    if status:
        if status not in ("pending_payment","paid","processing","shipped","delivered","cancelled"): error(422,"validation_error","Invalid order status")
        stmt=stmt.where(Order.status==status)
    rows=session.exec(stmt.order_by(Order.created_at.desc())).all(); return {"items":[order_out(o) for o in rows[(page-1)*20:page*20]],"page":page,"total":len(rows)}

@app.get("/orders/{order_id}")
def get_order(order_id:int,user:User=Depends(current_user),session:Session=Depends(get_session)): return order_out(owned_order(session,order_id,user))

@app.put("/orders/{order_id}/delivery")
def update_delivery(order_id:int,body:DeliveryIn,user:User=Depends(current_user),session:Session=Depends(get_session)):
    o=session.get(Order,order_id)
    if not o: error(404,"not_found","Order not found")
    if user.role!="admin":
        require_role(user,"vendor"); v=session.exec(select(Vendor).where(Vendor.user_id==user.id)).first()
        if not v or v.id!=o.vendor_id: error(403,"forbidden","Order is not owned by vendor")
    if o.status not in ("paid","processing","shipped","delivered"): error(409,"conflict","Order must be paid before delivery")
    o.delivery_status=body.status; o.tracking_reference=body.tracking_reference; o.delivery_note=body.note
    if body.status in ("processing","shipped","delivered"): o.status=body.status
    o.updated_at=now(); session.add(o); session.commit(); session.refresh(o); return order_out(o)

@app.get("/payments/{payment_id}")
def get_payment(payment_id:int,user:User=Depends(current_user),session:Session=Depends(get_session)):
    p=session.get(Payment,payment_id)
    if not p: error(404,"not_found","Payment not found")
    owned_order(session,p.order_id,user)
    if p.status=="pending" and p.checkout_request_id: refresh_payment_status(p,session)
    return payment_out(p)

def daraja_token():
    key=os.getenv("DARAJA_CONSUMER_KEY"); secret=os.getenv("DARAJA_CONSUMER_SECRET")
    if not key or not secret: raise RuntimeError("Daraja sandbox credentials are not configured")
    base=os.getenv("DARAJA_BASE_URL","https://sandbox.safaricom.co.ke").rstrip("/")
    if base != "https://sandbox.safaricom.co.ke": raise RuntimeError("Only the Daraja sandbox endpoint is allowed")
    r=httpx.get(base+"/oauth/v1/generate?grant_type=client_credentials",auth=(key,secret),timeout=DARAJA_TIMEOUT); r.raise_for_status(); return r.json()["access_token"],base

def daraja_password():
    shortcode=os.getenv("DARAJA_SHORTCODE"); passkey=os.getenv("DARAJA_PASSKEY")
    if not shortcode or not passkey: raise RuntimeError("Daraja sandbox configuration is incomplete")
    stamp=now().strftime("%Y%m%d%H%M%S"); return shortcode,base64.b64encode((shortcode+passkey+stamp).encode()).decode(),stamp

def refresh_payment_status(p:Payment,session:Session):
    try:
        token,base=daraja_token(); shortcode,password,stamp=daraja_password()
        r=httpx.post(base+"/mpesa/stkpushquery/v1/query",headers={"Authorization":f"Bearer {token}"},json={"BusinessShortCode":shortcode,"Password":password,"Timestamp":stamp,"CheckoutRequestID":p.checkout_request_id},timeout=DARAJA_TIMEOUT)
        r.raise_for_status(); payload=r.json()
        if payload.get("CheckoutRequestID") != p.checkout_request_id:
            return False
        code=int(payload.get("ResultCode",1))
        if code == 0:
            p.status = "succeeded"
            p.receipt_number = payload.get("MpesaReceiptNumber") or p.receipt_number
            order = session.get(Order, p.order_id)
            if not order:
                return False
            order.status = "paid"
            order.updated_at = now()
            session.add(order)
        elif code == 1032:
            p.status = "cancelled"
        elif code == 1037:
            p.status = "timed_out"
        elif code not in (1,):
            p.status = "failed"
        p.result_code = code
        session.add(p)
        session.commit()
        return True
    except Exception:
        return False

@app.post("/payments/mpesa/stkpush",status_code=202)
def create_stk(body:StkIn,user:User=Depends(current_user),session:Session=Depends(get_session)):
    o=owned_order(session,body.order_id,user)
    if user.role=="vendor": error(403,"forbidden","Only the customer may pay this order")
    if o.customer_id!=user.id: error(403,"forbidden","Only the order customer may pay")
    if o.status!="pending_payment": error(409,"conflict","Order is not awaiting payment")
    existing=session.exec(select(Payment).where(Payment.order_id==o.id,Payment.status=="pending")).first()
    if existing: return payment_out(existing)
    if len(body.phone)!=13 or not body.phone.startswith("+254") or body.phone[4] not in "17" or not body.phone[5:].isdigit(): error(422,"validation_error","Invalid Kenyan phone")
    try:
        token,base=daraja_token(); shortcode,password,stamp=daraja_password(); phone="254"+body.phone[4:]
        callback=os.getenv("DARAJA_CALLBACK_URL")
        if not callback or urlparse(callback).scheme!="https": raise RuntimeError("An HTTPS callback URL is required")
        payload={"BusinessShortCode":shortcode,"Password":password,"Timestamp":stamp,"TransactionType":os.getenv("DARAJA_TRANSACTION_TYPE","CustomerPayBillOnline"),"Amount":o.total_kes,"PartyA":phone,"PartyB":shortcode,"PhoneNumber":phone,"CallBackURL":callback,"AccountReference":f"BH-{o.id}","TransactionDesc":f"Order {o.id}"}
        r=httpx.post(base+"/mpesa/stkpush/v1/processrequest",headers={"Authorization":f"Bearer {token}"},json=payload,timeout=DARAJA_TIMEOUT); r.raise_for_status(); data=r.json()
        if data.get("ResponseCode")!="0" or not data.get("CheckoutRequestID"): raise RuntimeError("Daraja did not accept STK request")
        p=Payment(order_id=o.id,amount_kes=o.total_kes,checkout_request_id=data["CheckoutRequestID"],merchant_request_id=data.get("MerchantRequestID")); session.add(p); session.commit(); session.refresh(p); return payment_out(p)
    except Exception as exc: error(502,"upstream_error","Daraja sandbox request failed")

@app.post("/payments/mpesa/callback")
def mpesa_callback(body:dict[str,Any],session:Session=Depends(get_session)):
    try:
        cb=body["Body"]["stkCallback"]; checkout=cb["CheckoutRequestID"]; code=int(cb["ResultCode"]); merchant=cb["MerchantRequestID"]
    except Exception: error(400,"validation_error","Invalid Daraja callback shape")
    p=session.exec(select(Payment).where(Payment.checkout_request_id==checkout)).first()
    if not p: error(404,"not_found","Checkout request not found")
    if p.status!="pending": return {"accepted":True,"duplicate":True}
    if p.merchant_request_id and p.merchant_request_id!=merchant: error(400,"validation_error","Callback merchant request mismatch")
    metadata=cb.get("CallbackMetadata",{}).get("Item",[]); values={x.get("Name"):x.get("Value") for x in metadata if isinstance(x,dict)}
    if code==0:
        try:
            amount=int(values["Amount"]); receipt=str(values["MpesaReceiptNumber"])
        except Exception: error(400,"validation_error","Successful callback missing amount or receipt")
        if amount!=p.amount_kes: error(400,"validation_error","Callback amount mismatch")
    # Daraja callbacks are not cryptographically signed. Treat one as a signal
    # to query Daraja, not as authoritative proof of payment or failure.
    refresh_payment_status(p, session)
    return {"accepted":True,"duplicate":False}