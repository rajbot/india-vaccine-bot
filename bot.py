#!/usr/bin/env python3

import datetime
import json
import logging
import os
import requests
import time
from pathlib import Path


sleep_between_runs = 300
sleep_between_configs = 15

configs = [{
    "name": "Pune",
    "state": "maharashtra",
    "districts": ["Pune"],
    "alert_channel": "C020LSC1NFQ",
    "min_age_limit": 18,
    "min_pincode": 411000,
    "max_pincode": 412308,
}, {
    "name": "Bangalore",
    "state": "karnataka",
    "districts": ["Bangalore Rural", "Bangalore Urban"],
    "alert_channel": "C0216DGJBCH",
}, {
    "name": "Delhi",
    "state": "delhi",
    "alert_channel": "C020QLZ56UV",
}, {
    "name": "Gurugram",
    "state": "haryana",
    "districts": ["Gurgaon"],
    "alert_channel": "C020QKJASNR",
}, {
    "name": "Hyderabad",
    "state": "telangana",
    "districts": ["Hyderabad"],
    "alert_channel": "C021JPGHMR6",
}, {
    "name": "Hyderabad",
    "state": "telangana",
    "districts": ["Hyderabad"],
    "alert_channel": "C0217J5B8NM",
    "min_age_limit": 45,
}, {
    "name": "Mumbai",
    "state": "maharashtra",
    "districts": ["Mumbai"],
    "alert_channel": "C020U1L01FD",
}]


# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%m/%d/%Y %H:%M:%S",
)

logger = logging.getLogger("india-vaccine-bot")


# Load all districts
p = Path(__file__).with_name('districts.json')
with p.open() as fh:
    all_districts = json.load(fh)


# post_webhook()
#_________________________________________________________________________________________
def post_webhook(data, config):
    webhook_url = os.environ.get("WEBHOOK_URL")
    if webhook_url is None:
        logger.error("WEBHOOK_URL env var is not set")
        return

    response = requests.post(
        webhook_url,
        data=json.dumps(data),
        headers={'Content-Type': 'application/json'}
    )
    print(response)


# report_availability()
#_________________________________________________________________________________________
def report_availability(slots_by_date_pincode, config):
    keys = list(slots_by_date_pincode.keys())
    keys.sort()
    most_recent = keys[0]

    slots_by_pincode = slots_by_date_pincode[most_recent]

    num_slots = 0
    fields = []
    for pincode, slots in slots_by_pincode.items():
        print(pincode, slots)
        num_slots += slots["available_capacity"]
        num_centers = len(slots["centers"])

        if num_centers == 1:
            center_txt = slots["centers"][0]
        else:
            center_txt = f"{num_centers} centers"

        if slots['available_capacity'] == 1:
            num_txt = "One slot was found"
        else:
            num_txt = f"{slots['available_capacity']} slots were found"
        fields.append({
            "value": f"{num_txt} in pincode {pincode} at {center_txt}.",
            "short": False
        })

    min_age_limit = config.get("min_age_limit", 18)

    data = {
        "username": "VaxBot",
        "attachments": [{
            "pretext": f"{num_slots} appointment slots for {min_age_limit}+ found in {config['name']} on {most_recent.strftime('%b %d, %Y')}!",
            "fields": fields
        }]
    }

    if "alert_channel" in config:
        data["channel"] = config["alert_channel"]

    print(data)
    post_webhook(data, config)


# get_day_for_week()
#_________________________________________________________________________________________
def get_day_for_week(week):
    day = datetime.date.today() + datetime.timedelta(weeks=week)
    return day.strftime('%d-%m-%Y')


# check_district()
#_________________________________________________________________________________________
def check_district(d, week, config):
    params = {
        "district_id": d["district_id"],
        "date": get_day_for_week(week)
    }

    url = "https://cdn-api.co-vin.in/api/v2/appointment/sessions/public/calendarByDistrict"
    r = requests.get(url, params=params)
    data = r.json()

    print("district config is {d}", d)
    print("params", params)

    min_age_limit = config.get("min_age_limit", 18)

    slots_by_date_pincode = {}
    slots_found = False
    for center in data["centers"]:
        for session in center["sessions"]:
            #print(session)
            if session["min_age_limit"] > min_age_limit:
                continue

            if session["available_capacity"] == 0:
                continue

            if "min_pincode" in config:
                if center["pincode"] < config["min_pincode"]:
                    continue
            if "max_pincode" in config:
                if center["pincode"] > config["max_pincode"]:
                    continue

            slots_found = True
            date = datetime.datetime.strptime(session["date"], '%d-%m-%Y')

            slots_by_pincode = slots_by_date_pincode.get(date, {})
            slots = slots_by_pincode.get(center["pincode"], {})

            slots["available_capacity"] = slots.get("available_capacity", 0) + session["available_capacity"]
            slots["centers"] = slots.get("centers", []) + [center["name"]]

            slots_by_pincode[center["pincode"]] = slots
            slots_by_date_pincode[date] = slots_by_pincode

    #print(slots_by_date_pincode)
    return slots_found, slots_by_date_pincode




# check_availability()
#_________________________________________________________________________________________
def check_availability(config):
    state = config["state"]
    districts = config.get("districts")

    logger.info(f"Checking {state} {districts=}")

    if districts is None:
        districts_to_check = all_districts[state]["districts"]
    else:
        districts_to_check = [x for x in all_districts[state]["districts"] if x["district_name"] in districts]

    for d in districts_to_check:
        for week in range(0, 2):
            slots_found, slots_by_date_pincode = check_district(d, week, config)
            if slots_found:
                report_availability(slots_by_date_pincode, config)
                return


logger.info("Starting VaxBot")

while True:
    for config in configs:
        check_availability(config)
        time.sleep(sleep_between_configs)
    time.sleep(sleep_between_runs)