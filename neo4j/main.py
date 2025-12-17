from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from neo4j import GraphDatabase

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "pass1234"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class Address(BaseModel):
    city: str
    street: str
    house: str

class Owner(BaseModel):
    name: str

class Property(BaseModel):
    title: str
    type: str
    price: float
    area: float
    rooms: int
    address: Address
    owners: Optional[List[Owner]] = None

def run_query(query: str, params: dict = None):
    with driver.session() as session:
        result = session.run(query, params or {})
        return [record.data() for record in result]

@app.get("/addresses")
def get_addresses():
    query = "MATCH (a:Address) RETURN a.city AS city, a.street AS street, a.house AS house"
    return run_query(query)

@app.post("/addresses")
def create_address(addr: Address):
    query = """
    MERGE (a:Address {city:$city, street:$street, house:$house})
    RETURN a.city AS city, a.street AS street, a.house AS house
    """
    return run_query(query, addr.dict())[0]

@app.get("/owners")
def get_owners():
    query = "MATCH (o:Owner) RETURN o.name AS name"
    return run_query(query)

@app.post("/owners")
def create_owner(owner: Owner):
    query = "MERGE (o:Owner {name:$name}) RETURN o.name AS name"
    return run_query(query, owner.dict())[0]

@app.get("/properties")
def get_properties():
    query = """
    MATCH (p:Property)
    OPTIONAL MATCH (p)-[:LOCATED_AT]->(a:Address)
    OPTIONAL MATCH (p)-[:OWNED_BY]->(o:Owner)
    RETURN p.title AS title, p.type AS type, p.price AS price, p.area AS area, p.rooms AS rooms,
           a { .city, .street, .house } AS address,
           collect(DISTINCT o { .name }) AS owners
    """
    return run_query(query)

@app.post("/properties")
def create_property(prop: Property):
    prop.owners = prop.owners or []

    addr_query = """
    MERGE (a:Address {city:$city, street:$street, house:$house})
    RETURN a.city AS city, a.street AS street, a.house AS house
    """
    address_record = run_query(addr_query, prop.address.dict())[0]

    prop_query = """
    CREATE (p:Property {title:$title, type:$type, price:$price, area:$area, rooms:$rooms})
    WITH p
    MATCH (a:Address {city:$city, street:$street, house:$house})
    MERGE (p)-[:LOCATED_AT]->(a)
    RETURN p.title AS title, p.type AS type, p.price AS price, p.area AS area, p.rooms AS rooms,
           a { .city, .street, .house } AS address
    """
    prop_data = prop.dict()
    prop_data.update(prop.address.dict())
    property_record = run_query(prop_query, prop_data)[0]

    for owner in prop.owners:
        owner_query = """
        MERGE (o:Owner {name:$name})
        WITH o
        MATCH (p:Property {title:$title})
        MERGE (p)-[:OWNED_BY]->(o)
        """
        run_query(owner_query, {"name": owner.name, "title": prop.title})

    property_record["owners"] = [owner.dict() for owner in prop.owners]

    return property_record

@app.delete("/properties/{title}")
def delete_property(title: str):
    # Проверяем, существует ли объект
    check_query = "MATCH (p:Property {title:$title}) RETURN p"
    result = run_query(check_query, {"title": title})
    if not result:
        raise HTTPException(status_code=404, detail="Property not found")

    # Удаляем объект и все его связи
    delete_query = """
    MATCH (p:Property {title:$title})
    DETACH DELETE p
    """
    run_query(delete_query, {"title": title})
    return {"message": f"Property '{title}' deleted successfully"}