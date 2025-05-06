import requests
import csv
import json
import os
from datetime import datetime, timedelta, timezone
import certifi

# Force requests to use certifi's root CAs
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
SHOP_DOMAIN = os.getenv('SHOP_DOMAIN')
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
API_VERSION = os.getenv('API_VRSION')

def fetch_orders(limit=250, status="any", created_at_min=None):
    """
    Fetch all orders from the Shopify REST Admin API,
    including:
      - name            (store-facing "#1001")
      - customer        (registered customer object, if any)
      - shipping_address (guest checkout name)
      - billing_address  (fallback)
      - tags
      - fulfillments    (for shipment_status)
    """
    url = f"https://{SHOP_DOMAIN}/admin/api/{API_VERSION}/orders.json"
    headers = {
        "X-Shopify-Access-Token": ACCESS_TOKEN,
        "Content-Type": "application/json"
    }
    params = {
        "limit": limit,
        "status": status,
        "fields": ",".join([
            "name",
            "customer",
            "shipping_address",
            "billing_address",
            "created_at",
            "email",
            "total_price",
            "financial_status",
            "fulfillment_status",
            "currency",
            "tags",
            "fulfillments"
        ])
    }
    if created_at_min:
        params["created_at_min"] = created_at_min

    orders = []
    while True:
        r = requests.get(url, headers=headers, params=params, verify=certifi.where())  # Use certifi for SSL certs
        r.raise_for_status()
        batch = r.json().get("orders", [])
        if not batch:
            break
        orders.extend(batch)

        link = r.headers.get("Link", "")
        if 'rel="next"' not in link:
            break
        url = link.split("<")[1].split(">")[0]
        params = {}

    return orders

def extract_customer_name(order):
    """
    Return the customer name as shown in the Admin UI:
      1. Registered customer first+last
      2. Shipping address first+last
      3. Billing address first+last
      4. Email prefix
      5. "Guest"
    """
    # 1) registered customer
    cust = order.get("customer") or {}
    first = cust.get("first_name", "") or ""
    last  = cust.get("last_name", "")  or ""
    if first or last:
        return f"{first} {last}".strip()

    # 2) shipping address
    ship = order.get("shipping_address") or {}
    sf = ship.get("first_name", "") or ""
    sl = ship.get("last_name", "")  or ""
    if sf or sl:
        return f"{sf} {sl}".strip()

    # 3) billing address
    bill = order.get("billing_address") or {}
    bf = bill.get("first_name", "") or ""
    bl = bill.get("last_name", "")  or ""
    if bf or bl:
        return f"{bf} {bl}".strip()

    # 4) email prefix
    email = order.get("email", "") or ""
    if "@" in email:
        return email.split("@", 1)[0]

    # 5) fallback
    return "Guest"

def extract_customer_id(order):
    return (order.get("customer") or {}).get("id", "")

def extract_delivery_status(order):
    statuses = []
    for f in order.get("fulfillments", []):
        s = f.get("shipment_status")
        if s:
            statuses.append(s)
    return ", ".join(statuses) if statuses else "Not Available"

def extract_tags(order):
    return order.get("tags", "")

def save_orders_to_json(orders, filename):
    os.makedirs("docs/data", exist_ok=True)
    with open(filename, "w", newline="", encoding="utf-8") as f:
        json.dump(orders, f, indent=2)
    print(f"✅ Wrote {len(orders)} orders to {filename}")

if __name__ == "__main__":
    one_week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()  # Fixed UTC warning
    orders = fetch_orders(created_at_min=one_week_ago)
    save_orders_to_json(orders, "docs/data/orders.json")
