from datetime import datetime, timedelta;
from frappe_hfhg.frappe_hfhg.doctype.lead.lead import get_original_lead_name
import frappe
# from frappe.utils.data import today
import json

from frappe.share import _, set_permission
from frappe.utils import (
	add_days,
	cstr,
	get_first_day,
	get_last_day,
	getdate,
	month_diff,
	split_emails,
	today,
    add_months,get_weekday,formatdate
)
from datetime import datetime, timedelta
from  functools import reduce
from frappe.utils.password import update_password
from frappe.core.doctype.user import user

month_ago = (datetime.today() - timedelta(days=30)).strftime('%Y-%m-%d')
month_later = (datetime.today() + timedelta(days=30)).strftime('%Y-%m-%d')

full_access_roles = ["Lead Distributor", "HOD", "Marketing Head", "Accountant", "Lead checker", "Surbhi-backend"]

@frappe.whitelist()
def get_total_leads():
    user = frappe.session.user
    roles = frappe.get_roles()
    for full_access_role in full_access_roles:
        if full_access_role in roles:
            count = frappe.db.count('Lead')
            return {
                "value": count,
                "fieldtype": "Int",
                "route_options": {"from_date": "2024-01-01"},
                "route": ["lead"]
            }
    
    is_receptionist = frappe.db.exists("Receptionist", {'email': user})
    if is_receptionist:
        receptionist = frappe.db.get_value('Receptionist', {'email': user}, ['name', 'center'], as_dict=1)
        leads = frappe.get_all('Lead', filters={'center': receptionist.center})
        return {
            "value": len(leads),
            "fieldtype": "Int",
            "route_options": {"from_date": "2024-01-01"},
            "route": ["lead", "?center=" + receptionist.center]
        }

    is_executive = frappe.db.exists("Executive", {'email': user})
    if is_executive:
        executive = frappe.db.get_value('Executive', {'email': user}, ['name'], as_dict=1)
        leads = frappe.get_all('Lead', filters={'executive': executive.name})
        return {
            "value": len(leads),
            "fieldtype": "Int",
            "route_options": {"from_date": "2024-01-01"},
            "route": ["lead", "?executive=" + executive.name]
        }
    
    count = frappe.db.count('Lead')
    return {
        "value": count,
        "fieldtype": "Int",
        "route_options": {"from_date": "2024-01-01"},
        "route": ["lead"]
    }

@frappe.whitelist()
def get_open_reminders_count():
    user = frappe.session.user
    roles = frappe.get_roles()
    for full_access_role in full_access_roles:
        if full_access_role in roles:
            count =  frappe.db.count('Reminders', filters={'status': 'Open', 'date': ('between', [today(), month_later])})
            return {
                "value": count,
                "fieldtype": "Int",
                "route_options": {"from_date": today(), "to_date": month_later, "status": "Upcoming"},
                "route": ["query-report", "Reminder Report"]
            }

    is_receptionist = frappe.db.exists("Receptionist", {'email': user})
    if is_receptionist:
        receptionist = frappe.db.get_value('Receptionist', {'email': user}, ['name', 'center'], as_dict=1)
        leads = frappe.get_all('Lead', filters={'center': receptionist.center})
        total = 0
        for lead in leads:
            count =  frappe.db.count('Reminders', filters={'status': 'Open', 'date': ('between', [today(), month_later]), 'parent': lead.name})
            total = total + count

        return {
            "value": total,
            "fieldtype": "Int",
            "route_options": {"from_date": today(), "to_date": month_later, "status": "Upcoming"},
            "route": ["query-report", "Reminder Report"]
        }

    is_executive = frappe.db.exists("Executive", {'email': user})
    if is_executive:
        executive = frappe.db.get_value('Executive', {'email': user}, ['name'], as_dict=1)
        count =  frappe.db.count('Reminders', filters={'status': 'Open', 'date': ('between', [today(), month_later]), 'executive': executive.name})
        return {
            "value": count,
            "fieldtype": "Int",
            "route_options": {"from_date": today(), "to_date": month_later, "status": "Upcoming"},
            "route": ["query-report", "Reminder Report"]
        }

    count =  frappe.db.count('Reminders', filters={'status': 'Open', 'date': ('between', [today(), month_later])})
    return {
        "value": count,
        "fieldtype": "Int",
        "route_options": {"from_date": today(), "to_date": month_later, "status": "Upcoming"},
        "route": ["query-report", "Reminder Report"]
    }


@frappe.whitelist()
def get_all_reminders_count():
    user = frappe.session.user
    roles = frappe.get_roles()
    for full_access_role in full_access_roles:
        if full_access_role in roles:
            count =  frappe.db.count('Reminders', filters={'date': ('between', [today(), month_later])})
            return {
                "value": count,
                "fieldtype": "Int",
                "route_options": {"from_date": today(), "to_date": month_later},
                "route": ["query-report", "Reminder Report"]
            }

    is_receptionist = frappe.db.exists("Receptionist", {'email': user})
    if is_receptionist:
        receptionist = frappe.db.get_value('Receptionist', {'email': user}, ['name', 'center'], as_dict=1)
        leads = frappe.get_all('Lead', filters={'center': receptionist.center})
        total = 0
        for lead in leads:
            count =  frappe.db.count('Reminders', filters={'date': ('between', [today(), month_later]), 'parent': lead.name})
            total = total + count

        return {
            "value": total,
            "fieldtype": "Int",
            "route_options": {"from_date": today(), "to_date": month_later},
            "route": ["query-report", "Reminder Report"]
        }

    is_executive = frappe.db.exists("Executive", {'email': user})
    if is_executive:
        executive = frappe.db.get_value('Executive', {'email': user}, ['name'], as_dict=1)
        count =  frappe.db.count('Reminders', filters={'date': ('between', [today(), month_later]), 'executive': executive.name})
        return {
            "value": count,
            "fieldtype": "Int",
            "route_options": {"from_date": today(), "to_date": month_later},
            "route": ["query-report", "Reminder Report"]
        }

    count =  frappe.db.count('Reminders', filters={'date': ('between', [today(), month_later])})
    return {
        "value": count,
        "fieldtype": "Int",
        "route_options": {"from_date": today(), "to_date": month_later},
        "route": ["query-report", "Reminder Report"]
    }

@frappe.whitelist()
def get_closed_reminders_count():
    user = frappe.session.user
    roles = frappe.get_roles()
    for full_access_role in full_access_roles:
        if full_access_role in roles:
            count = frappe.db.count('Reminders', filters={'status': 'Close', 'date': ('between', [month_ago, today()])})

            return {
                "value": count,
                "fieldtype": "Int",
                "route_options": {"from_date": month_ago, "to_date": today(), "status": "Completed"},
                "route": ["query-report", "Reminder Report"]
            }

    is_receptionist = frappe.db.exists("Receptionist", {'email': user})
    if is_receptionist:
        receptionist = frappe.db.get_value('Receptionist', {'email': user}, ['name', 'center'], as_dict=1)
        leads = frappe.get_all('Lead', filters={'center': receptionist.center})
        total = 0
        for lead in leads:
            count =  frappe.db.count('Reminders', filters={'status': 'Close', 'date': ('between', [month_ago, today()]), 'parent': lead.name})
            total = total + count

        return {
            "value": total,
            "fieldtype": "Int",
            "route_options": {"from_date": month_ago, "to_date": today(), "status": "Completed"},
            "route": ["query-report", "Reminder Report"]
        }

    is_executive = frappe.db.exists("Executive", {'email': user})
    if is_executive:
        executive = frappe.db.get_value('Executive', {'email': user}, ['name'], as_dict=1)
        count =  frappe.db.count('Reminders', filters={'status': 'Close', 'date': ('between', [month_ago, today()]), 'executive': executive.name})
        return {
            "value": count,
            "fieldtype": "Int",
            "route_options": {"from_date": month_ago, "to_date": today(), "status": "Completed"},
            "route": ["query-report", "Reminder Report"]
        }

    count = frappe.db.count('Reminders', filters={'status': 'Close', 'date': ('between', [month_ago, today()])})

    return {
        "value": count,
        "fieldtype": "Int",
        "route_options": {"from_date": month_ago, "to_date": today(), "status": "Completed"},
        "route": ["query-report", "Reminder Report"]
    }

@frappe.whitelist()
def get_missed_reminders_count():
    user = frappe.session.user
    roles = frappe.get_roles()
    for full_access_role in full_access_roles:
        if full_access_role in roles:
            count = frappe.db.count('Reminders', filters={'status': 'Open', 'date': ('between', [month_ago, today()])})

            return {
                "value": count,
                "fieldtype": "Int",
                "route_options": {"from_date": month_ago, "to_date": today(), "status": "Missed"},
                "route": ["query-report", "Reminder Report"]
            }

    is_receptionist = frappe.db.exists("Receptionist", {'email': user})
    if is_receptionist:
        receptionist = frappe.db.get_value('Receptionist', {'email': user}, ['name', 'center'], as_dict=1)
        leads = frappe.get_all('Lead', filters={'center': receptionist.center})
        total = 0
        for lead in leads:
            count =  frappe.db.count('Reminders', filters={'status': 'Open', 'date': ('between', [month_ago, today()]), 'parent': lead.name})
            total = total + count

        return {
            "value": total,
            "fieldtype": "Int",
            "route_options": {"from_date": month_ago, "to_date": today(), "status": "Missed"},
            "route": ["query-report", "Reminder Report"]
        }

    is_executive = frappe.db.exists("Executive", {'email': user})
    if is_executive:
        executive = frappe.db.get_value('Executive', {'email': user}, ['name'], as_dict=1)
        count =  frappe.db.count('Reminders', filters={'status': 'Open', 'date': ('between', [month_ago, today()]), 'executive': executive.name})
        return {
            "value": count,
            "fieldtype": "Int",
            "route_options": {"from_date": month_ago, "to_date": today(), "status": "Missed"},
            "route": ["query-report", "Reminder Report"]
        }
    
    count = frappe.db.count('Reminders', filters={'status': 'Open', 'date': ('between', [month_ago, today()])})

    return {
        "value": count,
        "fieldtype": "Int",
        "route_options": {"from_date": month_ago, "to_date": today(), "status": "Missed"},
        "route": ["query-report", "Reminder Report"]
    }

@frappe.whitelist()
def get_today_reminders_count():
    user = frappe.session.user
    roles = frappe.get_roles()
    for full_access_role in full_access_roles:
        if full_access_role in roles:
            count = frappe.db.count('Reminders', filters={'status': 'Open', 'date': ('=', today())})
            return {
                "value": count,
                "fieldtype": "Int",
                "route_options": {"from_date": today(), "to_date": today(), "status": "Upcoming"},
                "route": ["query-report", "Reminder Report"]
            }

    is_receptionist = frappe.db.exists("Receptionist", {'email': user})
    if is_receptionist:
        receptionist = frappe.db.get_value('Receptionist', {'email': user}, ['name', 'center'], as_dict=1)
        leads = frappe.get_all('Lead', filters={'center': receptionist.center})
        total = 0
        for lead in leads:
            count =  frappe.db.count('Reminders', filters={'status': 'Open', 'date': ('=', today()), 'parent': lead.name})
            total = total + count

        return {
            "value": total,
            "fieldtype": "Int",
            "route_options": {"from_date": today(), "to_date": today(), "status": "Upcoming"},
            "route": ["query-report", "Reminder Report"]
        }

    is_executive = frappe.db.exists("Executive", {'email': user})
    if is_executive:
        executive = frappe.db.get_value('Executive', {'email': user}, ['name'], as_dict=1)
        count =  frappe.db.count('Reminders', filters={'status': 'Open', 'date': ('=', today()), 'executive': executive.name})
        return {
            "value": count,
            "fieldtype": "Int",
            "route_options": {"from_date": today(), "to_date": today(), "status": "Upcoming"},
            "route": ["query-report", "Reminder Report"]
        }


    count = frappe.db.count('Reminders', filters={'status': 'Open', 'date': ('=', today())})

    return {
        "value": count,
        "fieldtype": "Int",
        "route_options": {"from_date": today(), "to_date": today(), "status": "Upcoming"},
        "route": ["query-report", "Reminder Report"]
    }


@frappe.whitelist()
def get_upcoming_consultation_count():
    user = frappe.session.user
    roles = frappe.get_roles()
    for full_access_role in full_access_roles:
        if full_access_role in roles:
            count =  frappe.db.count('Consultation', filters={'status': 'Scheduled', 'date': ('between', [today(), month_later])})
            return {
                "value": count,
                "fieldtype": "Int",
                "route_options": {"from_date": today(), "to_date": month_later},
                "route": ["query-report", "Consultation Report"]
            }
    
    is_receptionist = frappe.db.exists("Receptionist", {'email': user})
    if is_receptionist:
        receptionist = frappe.db.get_value('Receptionist', {'email': user}, ['name', 'center'], as_dict=1)
        count =  frappe.db.count('Consultation', filters={'status': 'Scheduled', 'date': ('between', [today(), month_later]), 'center': receptionist.center})

        return {
            "value": count,
            "fieldtype": "Int",
            "route_options": {"from_date": today(), "to_date": month_later},
            "route": ["query-report", "Consultation Report"]
        }

    is_executive = frappe.db.exists("Executive", {'email': user})
    if is_executive:
        executive = frappe.db.get_value('Executive', {'email': user}, ['name'], as_dict=1)
        count =  frappe.db.count('Consultation', filters={'status': 'Scheduled', 'date': ('between', [today(), month_later]), 'executive': executive.name})
        return {
            "value": count,
            "fieldtype": "Int",
            "route_options": {"from_date": today(), "to_date": month_later},
            "route": ["query-report", "Consultation Report"]
        }

    count =  frappe.db.count('Consultation', filters={'status': 'Scheduled', 'date': ('between', [today(), month_later])})
    return {
        "value": count,
        "fieldtype": "Int",
        "route_options": {"from_date": today(), "to_date": month_later},
        "route": ["query-report", "Consultation Report"]
    }


@frappe.whitelist()
def get_upcoming_surgery_count():
    user = frappe.session.user
    roles = frappe.get_roles()
    for full_access_role in full_access_roles:
        if full_access_role in roles:
            count =  frappe.db.count('Surgery', filters={'surgery_status': 'Booked', 'surgery_date': ('between', [today(), month_later])})
            return {
                "value": count,
                "fieldtype": "Int",
                "route_options": {"from_date": today(), "to_date": month_later},
                "route": ["query-report", "Surgery Report"]
            }

    is_receptionist = frappe.db.exists("Receptionist", {'email': user})
    if is_receptionist:
        receptionist = frappe.db.get_value('Receptionist', {'email': user}, ['name', 'center'], as_dict=1)
        count =  frappe.db.count('Surgery', filters={'surgery_status': 'Booked', 'surgery_date': ('between', [today(), month_later]), 'center': receptionist.center})

        return {
            "value": count,
            "fieldtype": "Int",
            "route_options": {"from_date": today(), "to_date": month_later, "center": receptionist.center},
            "route": ["query-report", "Surgery Report"]
        }

    is_executive = frappe.db.exists("Executive", {'email': user})
    if is_executive:
        executive = frappe.db.get_value('Executive', {'email': user}, ['name'], as_dict=1)
        count =  frappe.db.count('Surgery', filters={'surgery_status': 'Booked', 'surgery_date': ('between', [today(), month_later]), 'executive': executive.name})
        return {
            "value": count,
            "fieldtype": "Int",
            "route_options": {"from_date": today(), "to_date": month_later, "executive": executive.name},
            "route": ["query-report", "Surgery Report"]
        }

    count =  frappe.db.count('Surgery', filters={'surgery_status': 'Booked', 'surgery_date': ('between', [today(), month_later])})
    return {
        "value": count,
        "fieldtype": "Int",
        "route_options": {"from_date": today(), "to_date": month_later},
        "route": ["query-report", "Surgery Report"]
    }


@frappe.whitelist()
def get_todays_surgery_count():
    user = frappe.session.user
    roles = frappe.get_roles()
    for full_access_role in full_access_roles:
        if full_access_role in roles:
            count =  frappe.db.count('Surgery', filters={'surgery_date': ('=', today())})
            return {
                "value": count,
                "fieldtype": "Int",
                "route_options": {"surgery_date": today()},
                "route": ["surgery", "view", "list"]
            }

    is_receptionist = frappe.db.exists("Receptionist", {'email': user})
    if is_receptionist:
        receptionist = frappe.db.get_value('Receptionist', {'email': user}, ['name', 'center'], as_dict=1)
        count =  frappe.db.count('Surgery', filters={'surgery_date': ('=', today()), 'center': receptionist.center})

        return {
            "value": count,
            "fieldtype": "Int",
            "route_options": {"surgery_date": today(), "center": receptionist.center},
            "route": ["surgery", "view", "list"]
        }

    is_executive = frappe.db.exists("Executive", {'email': user})
    if is_executive:
        executive = frappe.db.get_value('Executive', {'email': user}, ['name'], as_dict=1)
        count =  frappe.db.count('Surgery', filters={'surgery_date':('=', today()), 'executive': executive.name})
        return {
            "value": count,
            "fieldtype": "Int",
            "route_options": {"surgery_date": today(), "executive": executive.name},
            "route": ["surgery", "view", "list"]
        }

    count =  frappe.db.count('Surgery', filters={'surgery_date': ('=', today())})
    return {
        "value": count,
        "fieldtype": "Int",
        "route_options": {"surgery_date": today()},
        "route": ["surgery", "view", "list"]
    }

@frappe.whitelist()
def get_todays_consultation_count():
    user = frappe.session.user

    roles = frappe.get_roles()
    for full_access_role in full_access_roles:
        if full_access_role in roles:    
            count =  frappe.db.count('Consultation', filters={'date': ('=', today())})
            return {
                "value": count,
                "fieldtype": "Int",
                "route_options": {"date": today()},
                "route": ["consultation", "view", "list"]
            }
    
    is_receptionist = frappe.db.exists("Receptionist", {'email': user})
    if is_receptionist:
        receptionist = frappe.db.get_value('Receptionist', {'email': user}, ['name', 'center'], as_dict=1)
        count =  frappe.db.count('Consultation', filters={'date': ('=', today()), 'center': receptionist.center})

        return {
            "value": count,
            "fieldtype": "Int",
            "route_options": {"date": today(), "center": receptionist.center},
            "route": ["consultation", "view", "list"]
        }

    is_executive = frappe.db.exists("Executive", {'email': user})
    if is_executive:
        executive = frappe.db.get_value('Executive', {'email': user}, ['name'], as_dict=1)
        count =  frappe.db.count('Consultation', filters={'date':('=', today()), 'executive': executive.name})
        return {
            "value": count,
            "fieldtype": "Int",
            "route_options": {"date": today(), "executive": executive.name},
            "route": ["consultation", "view", "list"]   
        }

    count =  frappe.db.count('Consultation', filters={'date': ('=', today())})
    return {
        "value": count,
        "fieldtype": "Int",
        "route_options": {"date": today()},
        "route": ["consultation", "view", "list"]
    }


@frappe.whitelist(allow_guest=True)
def get_dropdown_options():
    data = {
        "Common": [
            {
                "gender": ["Male", "Female", "Other"]
            }
        ],
        "Lead": [
            {
                "treatment_type": ["Hair loss medicines", "PRP / GFC therapy", "Hair transplant", "Other"]
            },
            {
                "consultation_type": ["Online consultation", "In clinic consultation"]
            },
            {
                "planning_time": ["Within a week", "Within a month", "Not decided yet"]
            },
            {
                "status": ["New Lead", "Duplicate Lead" ,"Fake Lead", "Invalid Number", "Not Connected", "Not Interested", "Callback", 
                        "Connected", "CS Followup", "CS Lined Up", "HT CS Done", "Budget Issue", "Costing Done", 
                        "Hairfall PT", "Medi/PRP", "Booked", "Date Given", "HT Postpone", "BHT Followup", "HT Done", 
                        "HT Not Possible", "Alopecia Case", "Loan/EMI", "Beard HT", "2nd session", "HT Prospect"]
            },
            {
                "service": ["Hair transplant", "Beard transplant", "Hair fall", "Alopecia", "IHR"]
            },
            {
                "source": ["Website", "Website Form", "Google Adword", "Google GMB", "Facebook", "Instagram", "Hoarding", 
                        "References", "Youtube", "Youtuber", "Quora", "Pinterest", "Twitter", "Just dial", "Imported Data"]
            },
            {
                "mode": ["Call", "Whatsapp", "Walkin", "Workflow", "Afzal"]
            },
            {
                "ht_eligible": ["Eligible", "Not Eligible"]
            },
            {
                "ht_technique": ["FUE", "B-FUE", "I-FUE", "Big-FUE", "DHI"]
            },
            {
                "ht_sessions": ["Session 1", "Session 2", "Session 3", "Session 4", "Session 5"]
            },
            {
                "reminder_status": ["Open", "Close"]
            },
            {
                "distance": ["Near", "Far"]
            }
        ],
        "Costing": [
            {
                "prp": ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
                "technique": ["FUE", "B-FUE", "I-FUE", "Big-FUE", "DHI"],
                "payment_status": ["Prospect", "Booking", "Refunded"]
            }
        ],
        "Surgery": [
            {
                "prp": ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
                "technique": ["FUE", "B-FUE", "I-FUE", "Big-FUE", "DHI"],
                "payment_status": ["Paid", "Not Paid", "Refunded"],
                "followup": ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18"],
                "surgery_status": ["Booked", "Partially Completed", "Completed", "Cancelled"],
                "discount_type": ["Amount", "Percentage"],
                "blood_report": ["CBC", "RBS", "Bt ct", "HIV", "HCV", "HBSAG", "CRP", "PTINR", "VDRL"],
                "verify": ["Yes", "No"]
            }
        ],
        "Consultation": [
            {
                "status": ["Scheduled", "Booked", "Spot Booking","Non Booked", "Medi-PRP", "Not Visited", "Rescheduled"],
                "slot": ["12:00 AM", "12:30 AM", "01:00 AM", "01:30 AM", "02:00 AM", "02:30 AM", "03:00 AM", "03:30 AM", "04:00 AM", "04:30 AM", "05:00 AM", "05:30 AM", "06:00 AM", "06:30 AM", "07:00 AM", "07:30 AM", "08:00 AM", "08:30 AM", "09:00 AM", "09:30 AM", "10:00 AM", "10:30 AM", "11:00 AM", "11:30 AM", "12:00 PM", "12:30 PM", "01:00 PM", "01:30 PM", "02:00 PM", "02:30 PM", "03:00 PM", "03:30 PM", "04:00 PM", "04:30 PM", "05:00 PM", "05:30 PM", "06:00 PM", "06:30 PM", "07:00 PM", "07:30 PM", "08:00 PM", "08:30 PM", "09:00 PM", "09:30 PM", "10:00 PM", "10:30 PM", "11:00 PM", "11:30 PM"],
                "mode": ["Call", "In-Person"],
                "payment": ["FOC", "Paid"],
                "payment_status": ["Paid", "Not Paid"]
            }
        ],
        "Treatment": [
            {
                "treatment_type": ["Head to Head", "PRP"],
                "payment_status": ["Paid", "Not Paid", "Free"],
                "session_type": [ "Free Session", "Paid Session"]
            }
        ],
        "Followup": [
            {
                "status": ["Open", "Closed", "Cancelled"],
                "reference_type": ["Surgery", "Costing", "Treatment", "Consultation"]
            }
        ],
        "Payment": [
            {
                "type": ["Refund", "Payment"],
                "payment_type": ["Surgery", "Costing", "Treatment", "Consultation"],
                "payment_method": ["Card", "Cash", "Cheque", "Net Banking", "Bajaj Finance"]
            }
        ],
        "Call Logs": [
            {
                "status": ["Incoming", "Outgoing", "Missed"],
            }
        ],
        "Calendar": [
            {
                "type": ["ALL", "Surgery", "Treatment", "Consultation"]
            }
        ]
    }

    return data
 
@frappe.whitelist()   
def get_calendar_data(year, month, center = "ALL" , types  = "ALL" ):
    today = frappe.utils.today()
    start_date = datetime(year= int(year), month = int(month), day=1)
    start_date = datetime.strftime(start_date , "%Y-%m-%d")
    end_date = get_last_day(start_date)

    filters = {}
    if center !=  "ALL":
        filters["center"] = center    
    
    surgeries_docs = frappe.db.get_list('Surgery' ,filters={
        "surgery_date" : ["between", [start_date,end_date]],
        "status" : ["!=", "Cancelled"],
        **filters    
    }, fields = ["patient as name"  ,"surgery_date as date" , "center", "doctor", "contact_number" ,"total_amount", "status", "city", "executive","note", "surgery_status","lead_source","grafts","graft_price","technique","amount_paid","prp" ,"pending_amount","with_gst_amount","without_gst_amount"],ignore_permissions=True)
    
    surgery_entries = frappe.get_all("Graft Entry", filters={"date" : ["between", [start_date,end_date]]}, fields=["*"],ignore_permissions=True)
    surgeries = []
    for y in surgery_entries:
        surgery = frappe.get_doc("Surgery", y["parent"], fields=["*"],ignore_permissions=True)
        if center == "ALL" or surgery.center == center:
            surgeries.append({
            "type" : "Surgery",
            "date" : y["date"],
            "name": surgery.name,
            "doctor": surgery.doctor,
            "contact_number": surgery.contact_number,
            "center": surgery.center,
            "status" : surgery.surgery_status,
            "city" : surgery.city,
            "note" : surgery.note,
            "executive" : surgery.executive,
            "lead_source" : surgery.lead_source,
            "grafts" : surgery.grafts,
            "graft_price" : surgery.graft_price,
            "technique" : surgery.technique,
            "amount_paid" : surgery.amount_paid,
            "prp" : surgery.prp,
            "pending_amount" : surgery.pending_amount,
            "with_gst_amount" : surgery.with_gst_amount,
            "without_gst_amount" : surgery.without_gst_amount
            })
    
    for x in surgeries_docs:
        new_obj = {
                "type" : "Surgery",
                "date" : x["date"],
                "name": x["name"],
                "doctor": x["doctor"],
                "contact_number": x["contact_number"],
                "center": x["center"],
                "status" : x["surgery_status"],
                "city" : x["city"],
                "note" : x["note"],
                "executive" : x["executive"],
                "lead_source" : x["lead_source"],
                "grafts" : x["grafts"],
                "graft_price" : x["graft_price"],
                "technique" : x["technique"],
                "amount_paid" : x["amount_paid"],
                "prp" : x["prp"],
                "pending_amount" : x["pending_amount"],
                "with_gst_amount" : x["with_gst_amount"],
                "without_gst_amount" : x["without_gst_amount"]
            }
        if new_obj not in surgeries:
            surgeries.append(new_obj)
    
 
    surgery_till_date_income = frappe.db.sql("""
        select sum(total_amount) as income_till_date from `tabSurgery` where status = "Paid"             
    """,as_dict =  True)
    
    consultations = frappe.db.get_list('Consultation' ,filters={
        "date" : ["between", [start_date,end_date]],
        **filters
    }, fields = ["patient as name"  ,"date" , "center", "doctor", "phone as contact_number", "name as id", "total_amount", "payment_status", "payment_status as status", "slot", "executive","note", "city", "payment"],ignore_permissions=True )
    
    consultations_till_date_income = frappe.db.sql("""
        select sum(total_amount) as income_till_date from `tabConsultation` where payment_status = "Paid"             
    """,as_dict =  True)

    treatments = frappe.db.get_list('Treatment' ,filters={
        "procedure_date" : ["between", [start_date,end_date]],
         **filters
    }, fields = ["patient as name"  ,"procedure_date as date" , "center", "name as id", "total_amount", "status"],ignore_permissions=True )
    
    treatments_till_date_income = frappe.db.sql("""
        select sum(total_amount) as income_till_date from `tabTreatment` where status = "Paid"             
    """,as_dict =  True)
    
    result = {}
    result["income_till_today"]  = surgery_till_date_income[0].income_till_date if len(surgery_till_date_income) > 0 else 0 + consultations_till_date_income[0].income_till_date if len(consultations_till_date_income) > 0 else 0 + treatments_till_date_income[0].income_till_date if len(treatments_till_date_income) > 0 else 0
    match types:
        case "ALL":
            surgeries  = list(map(lambda x : {
                "type" : "Surgery",
                **x
            }, surgeries))
            consultations = list(map(lambda x : {
                "type" : "Consultation",
                "total_mount" : 0,
                **x
            }, consultations))
            treatments = list(map(lambda x : {
                "type" : "Treatment",
                "total_amount" : 0,
                **x
            }, treatments))
            data = surgeries + consultations + treatments
            result["data"] = data
            result["slots"] = len(data)
            surgery_income = reduce(lambda acc,x:  acc + (x["total_amount"] if "total_amount" in x and x["status"] == "Paid" else 0),  surgeries_docs, 0)
            treatment_income = reduce(lambda acc,x:  acc + (x["total_amount"] if "total_amount" in x and x["status"] == "Paid" else 0),  treatments, 0)
            consultation_income = reduce(lambda acc,x:  acc + (x["total_mount"] if "total_mount" in x and x["payment_status"] == "Paid" else 0),  consultations, 0)
            result["income"] =  surgery_income + treatment_income + consultation_income
        case "Surgery":
            data = list(map(lambda x : {
                "type" : "Surgery",
                **x
            }, surgeries))
            result["data"] = data
            result["slots"] = len(data)
            result["income"] =  reduce(lambda acc,x:  acc + (x["total_amount"] if "total_amount" in x and x["status"] == "Paid" else 0),  surgeries_docs, 0)
            result["income_till_today"] = surgery_till_date_income[0].income_till_date if len(surgery_till_date_income) > 0 else 0
        case "Treatment":
            data = list(map(lambda x : {
                "type" : "Treatment",
                **x
            }, treatments))
            result["data"] = data
            result["slots"] = len(data)
            result["income"] = reduce(lambda acc,x:  acc + (x["total_amount"] if "total_amount" in x and x["status"] == "Paid" else 0),  data, 0)
            result["income_till_today"] = treatments_till_date_income[0].income_till_date if len(treatments_till_date_income) > 0 else 0
        case "Consultation":
            data = list(map(lambda x : {
                "type" : "Consultation",
                **x
            }, consultations))
            result["data"] = data
            result["slots"] = len(data)
            result["income"] = reduce(lambda acc,x:  acc + (x["total_amount"] if "total_amount" in x and x["payment_status"] == "Paid" else 0),  consultations, 0)
            result["income_till_today"] = consultations_till_date_income[0].income_till_date if len(consultations_till_date_income) > 0 else 0
    return result

@frappe.whitelist()   
def get_centers():
    centers = frappe.db.get_all('Center' , fields="name",pluck="name")
    return centers

@frappe.whitelist()
def get_surgery_data(year, month, center = "ALL"):
    today = frappe.utils.today()
    start_date = datetime(year= int(year), month = int(month), day=1)
    start_date = datetime.strftime(start_date , "%Y-%m-%d")
    end_date = get_last_day(start_date)
    
    filters = {}
    if center !=  "ALL":
        filters["center"] = center    
    
    surgeries = frappe.db.get_list('Surgery' ,filters={
        "surgery_date" : ["between", [start_date,end_date]],
        **filters    
    }, fields = ["patient as name"  ,"surgery_date as date" , "center", "doctor", "contact_number" ,"total_amount", "status" ] ,ignore_permissions=True)
    
    count = frappe.db.sql("""
        select sum(total_amount) as income_till_date from `tabSurgery` where status = "Paid"              
    """,as_dict =  True)
    
    result = {}
    result["income_till_today"]  = count[0].income_till_date if len(count) > 0 else 0
    
    data = list(map(lambda x : {
                "type" : "Surgery",
                **x
            }, surgeries))
    new_list = []
    for x in data:
        surgery_entries = frappe.get_all("Graft Entry", filters={"parent": x["name"]}, fields=["*"],ignore_permissions=True)
        if len(surgery_entries) > 0:
            for y in surgery_entries:
                new_list.append({
                    "type" : "Surgery",
                    "date" : y["date"],
                    "name": x["name"],
                    "doctor": x["doctor"],
                    "contact_number": x["contact_number"],
                    "center": x["center"],
                })
    result["data"] = new_list
    result["slots"] = len(data)
    result["income"] =  reduce(lambda acc,x:  acc + (x["total_amount"] if "total_amount" in x else 0),  data, 0)
    return result       

@frappe.whitelist()
def get_treatment_data(year, month, center = "ALL"):
    today = frappe.utils.today()
    start_date = datetime(year= int(year), month = int(month), day=1)
    start_date = datetime.strftime(start_date , "%Y-%m-%d")
    end_date = get_last_day(start_date)
    
    filters = {}
    if center !=  "ALL":
        filters["center"] = center    
    
    treatments = frappe.db.get_list('Treatment' ,filters={
        "procedure_date" : ["between", [start_date,end_date]],
         **filters
    }, fields = ["patient as name"  ,"procedure_date" , "center", "name as id", "total_amount", "status"] ,ignore_permissions=True)
    
    treatments_till_date_income = frappe.db.sql("""
        select sum(total_amount) as income_till_date from `tabTreatment` where status = "Paid"             
    """,as_dict =  True)
    
    result = {}
    result["income_till_today"]  = treatments_till_date_income[0].income_till_date if len(treatments_till_date_income) > 0 else 0
    
    data = list(map(lambda x : {
                "type" : "Treatment",
                "total_amount" : 0,
                **x
            }, treatments))
    result["data"] = data
    result["slots"] = len(data)
    result["income"] = reduce(lambda acc,x:  acc + (x["total_amount"] if "total_amount" in x and x["status"] == "Paid" else 0),  data, 0)
    return result
       
@frappe.whitelist()
def get_consultation_data(year, month, center = "ALL"):
    today = frappe.utils.today()
    start_date = datetime(year= int(year), month = int(month), day=1)
    start_date = datetime.strftime(start_date , "%Y-%m-%d")
    end_date = get_last_day(start_date)
    
    filters = {}
    if center !=  "ALL":
        filters["center"] = center    
    
    consultations = frappe.db.get_list('Consultation' ,filters={
        "date" : ["between", [start_date,end_date]],
        **filters
    }, fields = ["patient as name"  ,"date" , "center", "doctor", "phone as contact_number", "name as id", "total_amount", "payment_status" ],ignore_permissions=True )
    
    consultations_till_date_income = frappe.db.sql("""
        select sum(total_amount) as income_till_date from `tabConsultation` where payment_status = "Paid"             
    """,as_dict =  True)

    result = {}
    result["income_till_today"]  = consultations_till_date_income[0].income_till_date if len(consultations_till_date_income) > 0 else 0
    
    data = list(map(lambda x : {
                "type" : "Consultation",
                "total_amount" : 0,
                **x
            }, consultations))
    result["data"] = data
    result["slots"] = len(data)
    result["income"] = reduce(lambda acc,x:  acc + (x["total_amount"] if "total_amount" in x and x["payment_status"] == "Paid" else 0),  consultations, 0)
    return result       

@frappe.whitelist()
def get_user_info():
    user = frappe.session.user
    if not user:
        return {}
    user = frappe.get_doc("User", user)

    roles = frappe.get_roles()
    role = "Guest"

    if "Surbhi-backend" in roles:
        role = "Surbhi-backend"
    elif "HOD" in roles:
        role = "HOD"
    elif "Accountant" in roles:
        role = "Accountant"
    elif "Lead Distributor" in roles:
        role = "Lead Distributor"
    elif "Marketing Head" in roles:
        role = "Marketing Head"
    elif "Lead checker" in roles:
        role = "Lead checker"
    elif "Campaign" in roles:
        role = "Campaign"
    elif "Followup Doctor" in roles:
        role = "Followup Doctor"
    elif "Doctor" in roles:
        role = "Doctor"
    elif "Executive" in roles:
        role = "Executive"
    elif "Receptionist" in roles:
        role = "Receptionist"
    else:
        role = "Guest"

    return { "email" : user.email, "name" : user.full_name, "mobile_no": user.mobile_no, "role": role}

@frappe.whitelist(allow_guest=True)
def get_refund_data():
    doctype = frappe.form_dict.get("doctype")
    patient = frappe.form_dict.get("patient")
    if not patient or not doctype:
        return {"status": "error", "message": frappe._("Missing parameters")}
    payments = frappe.get_all("Payment", filters={"type": "Payment", "payment_type": doctype, "patient": patient})
    if len(payments) > 0:
        refunds = frappe.get_all("Payment", filters={"type": "Refund", "refund_payment_id": payments[0].name}, fields=["*"])
        return refunds
    return []


@frappe.whitelist()
def reset_password():
    user = frappe.session.user
    new_password = frappe.form_dict.get("new_password")
    if not user:
        return {"status": "error", "message": frappe._("User is not logged in")}
    if not new_password:
        return {"status": "error", "message": frappe._("Missing parameters")}
    update_password(user, new_password)
    return {"status": "success", "message": frappe._("Password changed successfully")}

@frappe.whitelist(allow_guest=True)
def forgot_password():
    forgot_email = frappe.form_dict.get("email")
    if not forgot_email:
        return {"status": "error", "message": frappe._("Missing parameters")}
    user.reset_password(forgot_email)
    return {"status": "success", "message": frappe._("Reset password link has been sent.")}

@frappe.whitelist()
def get_user_role():
    user = frappe.session.user
    roles = frappe.get_roles()
    is_marketing_head = True if "Marketing Head" in roles else False
    if is_marketing_head:
        return {"role": "Marketing Head", "name": user, "executives": [], "center": None}
    is_receptionist = frappe.db.exists("Receptionist", {'email': user})
    if is_receptionist:
        receptionist = frappe.db.get_value('Receptionist', {'email': user}, ['name'], as_dict=1)
        center = frappe.db.get_value('Center', {'receptionist': receptionist.name}, ['name'], as_dict=1)
        if center:
            return {"role": "Receptionist", "name": receptionist, "center": center.name}
        else:
            center = frappe.db.get_value('Center', {'clinic_manager': user}, ['name'], as_dict=1)
            if center:
                return {"role": "Receptionist", "name": receptionist, "center": center.name}
            else:
                return {"role": "Guest", "name": user, "executives": [], "center": None}

    is_executive = frappe.db.exists("Executive", {'email': user})
    if is_executive:
        executive = frappe.db.get_value('Executive', {'email': user}, ['name'], as_dict=1)
        return {"role": "Executive", "name": executive, "executives": [], "center": None}

    return {"role": "Guest", "name": user, "executives": [], "center": None}

@frappe.whitelist(allow_guest=True)
def get_call_logs():
    timespan = frappe.form_dict.get("timespan")
    if not timespan:
        return {"status": "error", "message": frappe._("Missing parameters")}
    if timespan == "week":
        today = frappe.utils.today()
        start_date = frappe.utils.add_days(today, -7)
        end_date = today
    elif timespan == "month":
        today = frappe.utils.today()
        start_date = frappe.utils.add_months(today, -1)
        end_date = today
    elif timespan == "year":
        today = frappe.utils.today()
        start_date = frappe.utils.add_months(today, -12)
        end_date = today
    elif timespan == "today":
        start_date = frappe.utils.today()
        end_date = frappe.utils.today()
    else:
        return {"status": "error", "message": frappe._("Invalid timespan")}
    call_logs = frappe.get_all("Call Logs", filters={"datetime": ["between", [start_date, end_date]]}, fields=["*"])
    return {
        "incoming": {
            "total": len([call_log for call_log in call_logs if call_log.status == "Incoming"]),
            "duration": sum([call_log.duration for call_log in call_logs if call_log.status == "Incoming"])
        },
        "outgoing": {
            "total": len([call_log for call_log in call_logs if call_log.status == "Outgoing"]),
            "duration": sum([call_log.duration for call_log in call_logs if call_log.status == "Outgoing"])
        },
        "missed": {
            "total": len([call_log for call_log in call_logs if call_log.status == "Missed"]),
            "duration": sum([call_log.duration for call_log in call_logs if call_log.status == "Missed"])
        },
        "data": call_logs
    }

def format_phone_number(phone_number):
    digits_only = ''.join(filter(str.isdigit, phone_number))
    main_number = digits_only[-10:]
    country_code = digits_only[:-10] if len(digits_only) > 10 else "91"

    return f"+{country_code}-{main_number}"

def parse_date(date_str):
    try:
        date_obj = datetime.strptime(date_str, "%b %d, %Y %I:%M:%S %p")
        return date_obj.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        frappe.log_error(message=str(e), title="Date Parsing Error")
        return None
    
@frappe.whitelist(allow_guest=True)
def create_call_logs(call_logs):
    try:
        call_logs = frappe.parse_json(call_logs)
        
        for log in call_logs:
            call_log_doc = frappe.get_doc({
                "doctype": "Call Logs",
                "datetime": parse_date(log.get("dateTime")),
                "duration": log.get("duration"),
                "phone_number": format_phone_number(log.get("phoneNumber")),
                "timestamp": log.get("timestamp"),
                "status": log.get("type").capitalize(),
                "device_id": log.get("rawType"),
            })
            
            call_log_doc.insert(ignore_permissions=True)
        
        frappe.db.commit()
        return {"status": "success", "message": _("Call logs created successfully")}
    
    except Exception as e:
        frappe.log_error(message=str(e), title="Create Call Logs Error")
        return {"status": "error", "message": _("Failed to create call logs"), "error": str(e)}
    
banks = [
  "BHOPAL HAIRFREE AND HAIRGROW CLINIC LLP",
  "URBAN SKIN AND HAIR CLINIC LLP-MUMBAI",
  "HAIRFREE LASER PRIVATE LIMITED-SURAT",
  "HAIRFREE AND HAIRGROW KHARADE CLINIC LLP",
  "HAIRFREE LASER PRIVATE LIMITED-PUNE",
  "HAIRFREE LASER PRIVATE LIMITED-BANGLORE",
  "DERMAGLOW AND HFHG CLINIC LLP-DELHI",
  "PANKAJ KUMAR-HUF",
  "HIMALAYAS SKIN AND HAIR CLINIC-KOLKATA",
  "HAIR CITY CLINIC",
]

@frappe.whitelist(allow_guest=True)
def get_payment_in_options():
    type = frappe.request.args.get("type")
    if type == "Cash":
        payment_in = frappe.get_all("Payment In", filters={"name": ["not in", banks]}, fields=["name"])
        return list(payment_in.name for payment_in in payment_in)
    else:
        payment_in = frappe.get_all("Payment In", filters={"name": ["in", banks]}, fields=["name"])
        return list(payment_in.name for payment_in in payment_in)
        


@frappe.whitelist()
def get_patient_details(surgery_id):
    # Fetch surgery details from the database
    surgery = frappe.get_doc("Surgery", surgery_id)
    
    # Retrieve relevant patient details
    patient_details = {
        "patient_name": surgery.patient,
        "city": surgery.city,
        "contact_number": surgery.contact_number,
        "center": surgery.center,
        "doctor": surgery.doctor,
        "executive": surgery.executive,
        "surgery_status": surgery.surgery_status,
        "note":surgery.note
    }
    return patient_details

@frappe.whitelist(allow_guest=True, methods=["POST"])
def add_lead():
    data = frappe.form_dict
    if not data.get("contact_number") or not data.get("name") or not data.get("city"):
        return {"status": "error", "message": _("Please enter all required fields")}
    lead = frappe.new_doc("Lead")
    lead.executive = "Hiral"
    lead.center = "Unknown"
    lead.mode = "Workflow"
    lead.first_name = data.get("name")
    lead.contact_number = data.get("contact_number")
    lead.message = data.get("message", "")
    lead.city = data.get("city")
    lead.campaign_name = data.get("campaign_name")
    lead.source = data.get("source")
    lead.mode = "Workflow"
    frappe.set_user("info@hairfreehairgrow.com")
    lead.insert(ignore_permissions=True)
    return lead.name

@frappe.whitelist(allow_guest=True)
def find_mismatched_leads(contact_numbers):
    if not contact_numbers or not isinstance(contact_numbers, list):
        frappe.throw("Invalid input. Provide a list of contact numbers.")

    mismatched_leads = []

    for contact in contact_numbers:
        input_name = contact.get("name")
        contact_number = contact.get("contact_number")

        if not input_name or not contact_number:
            continue

        leads = frappe.get_all(
            "Lead",
            filters={"contact_number": contact_number},
            fields=["name", "contact_number"]
        )

        for lead in leads:
            if lead["name"] != input_name:
                mismatched_leads.append({
                    "name": input_name,
                    "contact_number": lead["contact_number"],
                    "lead_name": lead["name"]
                })

    return mismatched_leads



def format_phone_number(phone):
    if phone and len(phone) > 10:
        country_code = phone[:-10]
        local_number = phone[-10:]
        return f"{country_code}-{local_number}"
    return "+91-9999999999"

def format_city(city):
    if city:
        return city.strip().capitalize()
    return "Unknown" 

def format_description(description):
    if description:
        if description == '<p class="bn-inline-content" style="margin: 0.5em 0px; word-break: break-word;"></p>':
            return "--"
        return description
    return "--"

def format_mode(mode):
    if mode:
        new_mode = mode.strip().capitalize().replace(" ", "")
        if new_mode == "Walking":
            return "Walkin"
        if new_mode == "Whatsaap":
            return "Whatsapp"
        if new_mode not in ["Whatsapp", "Walkin"]:
            return "Workflow"
        return new_mode
    return mode

def format_center(mode):
    if mode:
        center = mode.strip().capitalize()
        if center in ["Test lead", "Pimple gurav", "F c road", "01857331123", "Pimple gaurav", "Pimple-gurav", "Pune"]:
            return "Pimple"
        if center == "Vapi silvasa" or center == "Silvassa" or center == "Silavassa" or center == "Vapi":
            return "Silvasa"
        if center == "Kochi" or center == "Hyd":   
            return "Hyderabad"
        if center == "Banglore":
            return "Bengaluru"
        if center == "Indore":
            return "Bhopal"
        if center == "Bihar" or center == "Gurgurum" or center == "Delhi":
            return "Gurugram"
        if center == "Nashik":
            return "Mumbai"
        if center == "Khardi":
            return "Kharadi"
        if center == "Ahmedabd" or center == "Ahemdabad" or center == "Ahmadabad" or center == "Ahmedbad":
            return "Ahmedabad"
        if center == "Suart" or center == "Surart" or center == "Nadiad" or center == "S" or center == "Na" or center == "9327286534":
            return "Surat"
        return center
    return "Unknown"

def format_status(status):
    if status == "Call Back" or status == "Call Back-FUP":
        return "Callback"
    elif status == "CS Follow Up":
        return "CS Followup"
    elif status == "EMI":
        return "Loan/EMI"
    elif status == "HT Posponded":
        return "HT Postpone"
    elif status == "BHT-FUP":
        return "BHT Followup"
    elif status == "HT Not Possible":
        return "HT Not Possible"
    elif status == "Appointment Fix":
        return "CS Lined Up"
    elif status == "Clinic Visit":
        return "HT CS Done"
    elif status == "Follow-up":
        return "BHT Followup"
    elif status == "Treatment Done":
        return "HT Done"
    else:
        return status  

def normalize_json(item):
    custom_fields = item.pop('custom_field', {})
    item.update(custom_fields)
    return item

def format_date(date_str):
    if date_str:
        try:
            date_obj = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return date_obj.strftime("%Y-%m-%d")
        except ValueError:
            return date_str
    return date_str


def get_doctor(center):
    if center == "Gurugram":
        return "Dr satpal sangwan"
    elif center == "Bhopal":
        return "Dr ankit jain"
    elif center == "Ahmedabad":
        return "Dr richa sanmukhani"
    elif center == "Mumbai":
        return "Dr nipun kesarkar"
    elif center == "Surat":
        return "Dr Jinkal Kunjadiya"
    elif center == "Pimple":
        return "Dr kiran chotaliya"
    elif center == "Kharadi":
        return "Dr Shreedevi"
    elif center == "Hyderabad":
        return "Dr pankaj khunt"
    elif center == "Kolkata":
        return "Dr pratibha pradhan"
    elif center == "Bengaluru":
        return "Dr Amera"
    elif center == "Nagpur":
        return "Dr sanjay sharma"
    elif center == "Silvasa":
        return "Dr Chintan Bhavsar"
    elif center == "Bangladesh":
        return "Dr uttam"
    else:
        return "Unknown Doctor"

def format_assign_by(assign_by, EXECUTIVE_EMAIL):
    if assign_by == "hitesh@hairfreehairgrow.com":
        return EXECUTIVE_EMAIL
    return assign_by

def farmat_status(status):
    if status == "Showed" or status == "Confirmed":
        return "Completed"
    return "Cancelled"

def farmat_status_consultation(status):
    if status == "Showed" or status == "Confirmed":
        return "Scheduled"
    return "Not Visited"

def convert_to_minutes(time_str):
    """Convert a 12-hour time string to total minutes from midnight."""
    time_obj = datetime.strptime(time_str, "%I:%M %p")
    return time_obj.hour * 60 + time_obj.minute


def get_closest_slot(date_str, all_slots):
    """Find the closest time slot to the given datetime."""
    input_datetime = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    input_minutes = input_datetime.hour * 60 + input_datetime.minute

    closest_slot = None
    smallest_difference = float("inf")

    for slot in all_slots:
        slot_minutes = convert_to_minutes(slot)
        difference = abs(input_minutes - slot_minutes)
        
        if difference < smallest_difference:
            smallest_difference = difference
            closest_slot = slot

    return closest_slot

all_slots = [
    "12:00 AM", "12:30 AM", "01:00 AM", "01:30 AM", "02:00 AM", "02:30 AM",
    "03:00 AM", "03:30 AM", "04:00 AM", "04:30 AM", "05:00 AM", "05:30 AM",
    "06:00 AM", "06:30 AM", "07:00 AM", "07:30 AM", "08:00 AM", "08:30 AM",
    "09:00 AM", "09:30 AM", "10:00 AM", "10:30 AM", "11:00 AM", "11:30 AM",
    "12:00 PM", "12:30 PM", "01:00 PM", "01:30 PM", "02:00 PM", "02:30 PM",
    "03:00 PM", "03:30 PM", "04:00 PM", "04:30 PM", "05:00 PM", "05:30 PM",
    "06:00 PM", "06:30 PM", "07:00 PM", "07:30 PM", "08:00 PM", "08:30 PM",
    "09:00 PM", "09:30 PM", "10:00 PM", "10:30 PM", "11:00 PM", "11:30 PM"
]

@frappe.whitelist(allow_guest=True)
def upload_leads():
    try:
        uploaded_file = frappe.request.files.get('file')
        if not uploaded_file:
            frappe.throw("No file uploaded")

        executive = frappe.form_dict.get('executive')
        executive_email = frappe.form_dict.get('executive_email')
        frappe.set_user("info@hairfreehairgrow.com")
        if not executive and not executive_email:
            frappe.throw("Executive and Executive email parameter is required")

        data = json.load(uploaded_file)

        if not isinstance(data, list):
            frappe.throw("Invalid data format. Expected a list of lead objects.")

        failed_objects_errors = []
        failed_objects = []

        for lead in data:
            lead = normalize_json(lead)
            created_objects = []
            try:
                lead_doc = frappe.get_doc({
                    "doctype": "Lead",
                    "first_name": lead.get("name_pure", "Missing Name"),
                    "email": lead.get("email"),
                    "contact_number": format_phone_number(lead.get("phone")),
                    "city": format_city(lead.get("city")),
                    "status": format_status(lead.get("status", {}).get("name")),
                    "center": format_center(lead.get("Center")),
                    "mode": format_mode(lead.get("Lead Mode")),
                    "created_on": format_date(lead.get("date_created")),
                    "ticket_number": lead.get("ticket_number"),
                    "campaign_name": lead.get("Campaign name"),
                    "message": lead.get("Message"),
                    "address": lead.get("fullAddressLine"),
                    "source": "Imported Data",
                    "imported_source": lead.get("source_id"),
                    "executive": executive,
                    "assign_by": executive_email
                })

                for note in lead.get("notes", []):
                    lead_doc.append("conversations", {
                        "description": note.get("description"),
                        "date": format_date(note.get("date_created"))
                    })

                for task in lead.get("task", []):
                    lead_doc.append("reminders", {
                        "status": "Close",
                        "description": task.get("description"),
                        "date": format_date(task.get("due_date")),
                    })

                lead_doc.insert(ignore_permissions=True)
                created_objects.append(lead_doc)

                booking = []
                surgeries = []
                consultations = []
                booking_added = False

                for appointment in lead.get("appointment", []):
                    if appointment.get("appointment_type") == "660e2bfec377c63a9eee51a4":
                        consultations.append(appointment)
                    else:
                        if not booking_added:
                            booking.append(appointment)
                            booking_added = True
                        surgeries.append(appointment)

                for booking_item in booking:
                    booking_doc = frappe.new_doc("Costing")
                    booking_doc.patient = lead_doc.name
                    booking_doc.note = booking_item.get('appointment_title', '') + "\n" + booking_item.get('appointment_desctiption', '')
                    booking_doc.executive = executive
                    booking_doc.assign_by = format_assign_by(booking_item.get("assign_by_detail", {}).get("email", ""), executive_email)
                    booking_doc.technique = "B-FUE"
                    booking_doc.booking_date = format_date(booking_item.get("appointment_start_date_time"))
                    booking_doc.doctor = get_doctor(lead_doc.center)
                    booking_doc.insert(ignore_permissions=True)
                    created_objects.append(booking_doc)

                if len(surgeries) > 0:
                    surgery_item = surgeries[0]
                    surgery_doc = frappe.new_doc("Surgery")
                    surgery_doc.patient = lead_doc.name
                    surgery_doc.note = surgery_item.get('appointment_title', '') + "\n" + surgery_item.get('appointment_desctiption', '')
                    surgery_doc.status = farmat_status(surgery_item.get('appointment_status', ''))
                    surgery_doc.surgery_date = format_date(surgery_item.get("appointment_start_date_time"))
                    surgery_doc.doctor = get_doctor(lead_doc.center)
                    surgery_doc.grafts = 100
                    surgery_doc.status = "Paid"

                    for surgery_entry in surgeries:
                        surgery_doc.append("grafts_surgeries", {
                            "note": surgery_entry.get('appointment_title', '') + "\n" + surgery_entry.get('appointment_desctiption', ''),
                            "date": format_date(surgery_entry.get("appointment_start_date_time")),
                            "grafts": 10
                        })
                    surgery_doc.insert(ignore_permissions=True)
                    created_objects.append(surgery_doc)

                for consultation_item in consultations:
                    consultation_doc = frappe.new_doc("Consultation")
                    consultation_doc.patient = lead_doc.name
                    consultation_doc.note = consultation_item.get('appointment_title', '') + "\n" + consultation_item.get('appointment_desctiption', '')
                    consultation_doc.executive = executive
                    consultation_doc.assign_by = format_assign_by(consultation_item.get("assign_by_detail", {}).get("email", ""), executive_email)
                    consultation_doc.status = farmat_status_consultation(consultation_item.get('appointment_status', ''))
                    consultation_doc.consultation_date = format_date(consultation_item.get("appointment_start_date_time"))
                    consultation_doc.doctor = get_doctor(lead_doc.center)
                    consultation_doc.payment_status = "Paid"
                    consultation_doc.mode = "In-Person"
                    consultation_doc.date = format_date(consultation_item.get("appointment_start_date_time"))
                    consultation_doc.slot = get_closest_slot(consultation_item.get("appointment_start_date_time", ""), all_slots)
                    consultation_doc.insert(ignore_permissions=True)
                    created_objects.append(consultation_doc)

            except Exception as e:
                for obj in reversed(created_objects):
                    try:
                        obj.delete(ignore_permissions=True)
                    except Exception as rollback_error:
                        frappe.log_error(f"Rollback failed for {obj.doctype}: {str(rollback_error)}")

                failed_objects_errors.append({
                    "error": str(e),
                    "lead": lead.get("name_pure", "Unknown"),
                    "phone": lead.get("phone", "Unknown"),
                    "doctype": obj.doctype if created_objects else "Unknown"
                })
                failed_objects.append(lead_doc)
                continue

        return {
            "status": "success",
            "message": "Leads processed successfully",
            "total_leads": len(data),
            "success_leads": len(data) - len(failed_objects_errors),
            "failed_objects": failed_objects,
            "failed_objects_errors": failed_objects_errors,
        }

    except Exception as e:
        frappe.log_error(str(e), "Lead Upload Error")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def get_campaign_names():
    meta_campaigns = frappe.get_all("Meta Campaign", fields=["campaign_name"])
    return [""] + [meta_campaign.campaign_name for meta_campaign in meta_campaigns]

@frappe.whitelist()
def get_ad_names():
    meta_ads = frappe.get_all("Meta Ads", fields=["ads_name"])
    return [""] + [meta_ad.ads_name for meta_ad in meta_ads]

@frappe.whitelist()
def create_user_device(user, device_id, device_name):
    if not user or not device_id:
        return {"status": "error", "message": "Missing parameters"}

    device_exists = frappe.get_all("User Device", filters={"user": user, "device_id": device_id})
    if device_exists:
        return {"status": "success", "message": "Device already exists for this user"}

    user_device = frappe.new_doc("User Device")
    user_device.user = user
    user_device.device_name = device_name if device_name else "Unknown"
    user_device.device_id = device_id
    user_device.save(ignore_permissions=True)

    return {"status": "success", "message": "Device created successfully"}

from frappe.desk.doctype.notification_log.notification_log import NotificationLog
from frappe_hfhg.firebase_utils import send_push_notification

class CustomNotificationLog(NotificationLog):
    def before_save(self):
        tokens = frappe.get_all("User Device", fields=["device_id"], filters={"user": self.for_user})
        for token in tokens:
            send_push_notification(token.get("device_id"), self.subject, self.email_content)

@frappe.whitelist()
def get_lead_change_history(lead_name):
    history = []

    lead_changes = frappe.get_all(
        "Version",
        filters={"docname": lead_name, "ref_doctype": "Lead"},
        fields=["ref_doctype", "data", "modified", "modified_by"],
        order_by="modified desc"
    )
    for change in lead_changes:
        data = frappe.parse_json(change.data)
        
        old_value = {}
        new_value = {}
        for field_change in data.get("added", []):
            child_table_name, child_data = field_change
            if isinstance(child_data, dict):
                new_value[child_table_name] = child_data

        for field_change in data.get("changed", []):
            if isinstance(field_change, list) and len(field_change) == 3:
                field_name, old, new = field_change
                old_value[field_name] = old
                new_value[field_name] = new
        for row_change in data.get("row_changed", []):
            if isinstance(row_change, list) and len(row_change) == 4:
                child_table, row_index, row_name, row_changes = row_change
                if child_table not in old_value:
                    old_value[child_table] = {}
                if child_table not in new_value:
                    new_value[child_table] = {}

                for field_change in row_changes:
                    if isinstance(field_change, list) and len(field_change) == 3:
                        field_name, old, new = field_change
                        if row_name not in old_value[child_table]:
                            old_value[child_table][row_name] = {}
                            new_value[child_table][row_name] = {}
                        old_value[child_table][row_name][field_name] = old
                        new_value[child_table][row_name][field_name] = new

        for field_change in data.get("removed", []):
            child_table_name, child_data = field_change
            if isinstance(child_data, dict):
                old_value[child_table_name] = child_data
        history.append({
            "doctype": "Lead",
            "type": "change",
            "name": lead_name,
            "old_value": frappe.as_json(old_value),
            "new_value": frappe.as_json(new_value),
            "modified": change.modified,
            "modified_by": change.modified_by
        })

    related_doctypes = ["Surgery", "Costing", "Consultation"]
    for doctype in related_doctypes:
        related_changes = frappe.get_all(
            "Version",
            filters={"ref_doctype": doctype, "docname": ["like", f"{lead_name}%"]},
            fields=["ref_doctype", "data", "modified", "modified_by", "docname"],
            order_by="modified desc"
        )
        for change in related_changes:
            data = frappe.parse_json(change.data)

            old_value = {}
            new_value = {}

            for field_change in data.get("added", []):
                child_table_name, child_data = field_change
                if isinstance(child_data, dict):
                    new_value[child_table_name] = child_data

            for field_change in data.get("changed", []):
                if isinstance(field_change, list) and len(field_change) == 3:
                    field_name, old, new = field_change
                    old_value[field_name] = old
                    new_value[field_name] = new

            for row_change in data.get("row_changed", []):
                if isinstance(row_change, list) and len(row_change) == 4:
                    child_table, row_index, row_name, row_changes = row_change
                    if child_table not in old_value:
                        old_value[child_table] = {}
                    if child_table not in new_value:
                        new_value[child_table] = {}

                    for field_change in row_changes:
                        if isinstance(field_change, list) and len(field_change) == 3:
                            field_name, old, new = field_change
                            if row_name not in old_value[child_table]:
                                old_value[child_table][row_name] = {}
                                new_value[child_table][row_name] = {}
                            old_value[child_table][row_name][field_name] = old
                            new_value[child_table][row_name][field_name] = new

            for field_change in data.get("removed", []):
                child_table_name, child_data = field_change
                if isinstance(child_data, dict):
                    old_value[child_table_name] = child_data

            history.append({
                "doctype": doctype,
                "type": "change",
                "name": change.docname,
                "old_value": frappe.as_json(old_value),
                "new_value": frappe.as_json(new_value),
                "modified": change.modified,
                "modified_by": change.modified_by
            })

    lead_creation = frappe.get_doc("Lead", lead_name, ["name", "created_on", "owner"])
    history.append({
        "doctype": "Lead",
        "type": "creation",
        "name": lead_creation.name,
        "old_value": "",
        "new_value": "",
        "modified": datetime.combine(lead_creation.created_on, datetime.min.time()),
        "modified_by": lead_creation.owner
    })

    consultations = frappe.get_all(
        "Consultation",
        filters={"patient": lead_name},
        fields=["name", "creation", "owner"],
    )
    for consultation in consultations:
        history.append({
            "doctype": "Consultation",
            "type": "creation",
            "name": consultation.name,
            "old_value": "",
            "new_value": "",
            "modified": consultation.creation,
            "modified_by": consultation.owner
        })
    
    costings = frappe.get_all(
        "Costing",
        filters={"patient": lead_name},
        fields=["name", "creation", "owner"],
    )
    for costing in costings:
        surgery_exists = frappe.db.exists("Surgery", {"patient": costing.name})
        if surgery_exists:
            surgery = frappe.get_doc("Surgery", costing.name, ["name", "creation", "owner"])
            history.append({
                "doctype": "Surgery",
                "type": "creation",
                "name": surgery.name,
                "old_value": "",
                "new_value": "",
                "modified": surgery.creation,
                "modified_by": surgery.owner
            })
        history.append({
            "doctype": "Costing",
            "type": "creation",
            "name": costing.name,
            "old_value": "",
            "new_value": "",
            "modified": costing.creation,
            "modified_by": costing.owner
        })


    history.sort(key=lambda x: x["modified"], reverse=True)
    return history

@frappe.whitelist(allow_guest=True)
def update_lead_status(lead_name, status):
    lead = frappe.get_doc("Lead", lead_name)
    lead.status = status
    lead.save(ignore_permissions=True)
    return lead

@frappe.whitelist(allow_guest=True)
def update_doc_info(doc, doc_name, field, value):
    document = frappe.get_doc(doc, doc_name)
    document.set(field, value)
    document.save(ignore_permissions=True)
    return document

@frappe.whitelist(allow_guest=True)
def update_reminder_executives():
  
    frappe.db.sql("""
        UPDATE `tabReminders` r
        JOIN `tabLead` l ON r.parent = l.name
        SET r.executive = l.executive
        WHERE r.status = 'Open'
        AND l.executive IS NOT NULL 
        AND l.previous_executive IS NOT NULL
        AND r.executive != l.executive
    """)
      
    frappe.db.commit()  

    return f"Updated reminders with the lead's executive."

@frappe.whitelist()
def get_user_notifications(limit_start=0, limit_page_length=10, read=0):
    user = frappe.session.user
    if int(read) != 0 and int(read) != 1:
        return frappe.throw("read must be 0 or 1")  

    notifications = frappe.get_all(
        'Notification Log',
        filters={'for_user': user, 'read': 1 if int(read) == 1 else 0},  
        fields=['name', 'subject', 'email_content', 'creation', 'read', 'document_name', 'document_type', 'from_user'],
        order_by='creation desc',
        limit_start=int(limit_start),
        limit_page_length=int(limit_page_length)
    )
    
    return notifications

from frappe.utils.global_search import search

@frappe.whitelist()
def custom_global_search(text, start=0, limit=20):
    if text and len(text) >= 5:
        doctype = "Lead"

        results = frappe.db.sql("""
            SELECT name, status, contact_number FROM `tab{doctype}`
            WHERE contact_number LIKE %s OR name LIKE %s OR alternative_number LIKE %s
        """.format(doctype=doctype), (f"%{text}%", f"%{text}%", f"%{text}%"))
        search_results = []
        for result in results:
            search_results.append({
                "doctype": doctype,
                "content": "Status: " + result[1] + " ||| " + "Contact Number: " + result[2],
                "name": result[0],
                "rank": 1
            })
        return search_results
    
    return search(text, start, limit)

def after_insert_lead_logs(lead, method):
    original_lead = get_original_lead_name(lead.contact_number, lead.alternative_number)
    original_lead_doc = None
    if_condition_result = "original_lead_doc is not None"
    if original_lead:
        original_lead_doc = frappe.get_doc("Lead", original_lead)
        if_condition_result = original_lead_doc.name == lead.name 
    log_doc = frappe.get_doc({
        "doctype": "After Insert Lead Log",
        "lead": lead.name,
        "status": lead.status,
        "executive": lead.executive,
        "contact": lead.contact, 
        "creation1": lead.creation,
        "lead_owner": lead.owner,
        "contact_number": lead.contact_number,
        "alternative_number": lead.alternative_number,
        "if_condition_result": if_condition_result,
        "object": json.dumps(lead.as_dict(), default=str),
        "original_lead": json.dumps(original_lead_doc.as_dict(), default=str) if original_lead_doc else None
    })

    log_doc.save(ignore_permissions=True)


@frappe.whitelist(allow_guest=True)
def get_form_data():
    executive=frappe.get_all("Executive",fields=["*"])
    center=frappe.get_all("Center",fields=["*"])
    return {"executive":executive,"center":center}

@frappe.whitelist(allow_guest=True)
def get_leadmapping_fields():
    fields = frappe.get_single("WhatsApp Settings")
    mappings = {"lead_reference_doctype": fields.lead_reference_doctype}

    field_mappings = []

    if fields.whatsapp_lead_field_mapping:
        for field in fields.whatsapp_lead_field_mapping:
            field_mapping = {
                key: value for key, value in field.as_dict().items()
                if key not in ["name", "creation", "modified", "modified_by", "owner", "idx", "docstatus"]
            }
            field_mapping["linked_records"] = []
            field_mapping["select_options"]=[]
            
            if field.doctype_field_type == "Select" and field.options:
                options_list = field.options.split(" ")
                field_mapping["select_options"]=options_list
                field_mapping["linked_records"] = []
                
                
            
            elif field.doctype_field_type == "Link":
                linked_doctype = frappe.get_meta(fields.lead_reference_doctype).get_field(field.lead_field_value).options
                field_mapping["linked_records"] = frappe.get_all(linked_doctype, fields=["name"])
                field_mapping["select_options"]=[]
            field_mappings.append(field_mapping)

    return {"mappings": mappings, "field_mappings": field_mappings}


    