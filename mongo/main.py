from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from bson import ObjectId
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client.realestate
addresses = db.addresses
owners = db.owners
properties = db.properties

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

class AddressModel(BaseModel):
    city: str
    street: str
    house: str

class OwnerModel(BaseModel):
    name: str

class OwnerShareModel(BaseModel):
    owner_id: str
    share: float

class PropertyModel(BaseModel):
    title: str
    type: str
    price: int
    area: int
    rooms: int
    amenities: List[str] = []
    address_id: str
    owners: List[OwnerShareModel]

def serialize_property(p):
    p["_id"] = str(p["_id"])
    if "address_id" in p:
        addr = addresses.find_one({"_id": ObjectId(p["address_id"])})
        p["address"] = {"city": addr["city"], "street": addr["street"], "house": addr["house"]} if addr else None
    if "owners" in p:
        for o in p["owners"]:
            owner = owners.find_one({"_id": ObjectId(o["owner_id"])})
            o["owner"] = {"name": owner["name"]} if owner else None
    return p

@app.post("/addresses")
def create_address(addr: AddressModel):
    res = addresses.insert_one(addr.dict())
    return {"_id": str(res.inserted_id)}

@app.get("/addresses")
def get_addresses():
    return [dict(a, _id=str(a["_id"])) for a in addresses.find()]

@app.post("/owners")
def create_owner(owner: OwnerModel):
    res = owners.insert_one(owner.dict())
    return {"_id": str(res.inserted_id)}

@app.get("/owners")
def get_owners():
    return [dict(o, _id=str(o["_id"])) for o in owners.find()]

@app.post("/properties")
def create_property(prop: PropertyModel):
    data = prop.dict()
    res = properties.insert_one(data)
    return {"_id": str(res.inserted_id)}

@app.get("/properties")
def get_properties():
    return [serialize_property(p) for p in properties.find()]

@app.get("/properties/all")
def get_all_properties():
    return [serialize_property(p) for p in properties.find()]

@app.get("/properties/price_above/{value}")
def properties_price_above(value: int):
    return [serialize_property(p) for p in properties.find({"price": {"$gt": value}})]

@app.get("/properties/type/{ptype}")
def properties_by_type(ptype: str):
    return [serialize_property(p) for p in properties.find({"type": ptype})]

@app.get("/properties/filter")
def filter_properties(min_area:int=0, max_price:int=1_000_000_000):
    result = properties.find({"$and":[{"area":{"$gt":min_area}}, {"price":{"$lt":max_price}}]})
    return [serialize_property(p) for p in result]

@app.get("/properties/by_owner/{owner_id}")
def properties_by_owner(owner_id: str):
    result = properties.find({"owners": {"$elemMatch": {"owner_id": owner_id}}})
    return [serialize_property(p) for p in result]

@app.get("/properties/sorted")
def properties_sorted(skip:int=0, limit:int=5):
    result = properties.find().sort("price", -1).skip(skip).limit(limit)
    return [serialize_property(p) for p in result]

@app.delete("/properties/{id}")
def delete_property(id: str):
    res = properties.delete_one({"_id": ObjectId(id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Property not found")
    return {"status": "deleted"}
