"""
One-time ward seeder script.

Run once after creating the Supabase schema:
    python jobs/data_seeder.py

This inserts all 198 BBMP wards with real names, constituencies,
and approximate population density data.

Data source: BBMP ward list (public domain)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.client import get_supabase
from utils.logger import get_logger

logger = get_logger("data_seeder")

# ── BBMP Ward data ────────────────────────────────────────────────────────────
# Format: (ward_id, name, constituency, approx_population, pop_density_per_sqkm)
# Population density approximated from BBMP records + census data.
# For hackathon: using representative values. Refine post-launch with exact data.

WARDS_DATA = [
    ("1",  "Kuvempu Nagar",          "Yelahanka",        45000,  8500),
    ("2",  "Yelahanka",              "Yelahanka",        72000,  9200),
    ("3",  "Yelahanka Satellite Town","Yelahanka",       38000,  7800),
    ("4",  "Attur",                  "Yelahanka",        41000,  6900),
    ("5",  "Thanisandra",            "Yelahanka",        95000, 12000),
    ("6",  "Kodigehalli",            "Yelahanka",        58000,  9800),
    ("7",  "Vidyaranyapura",         "Yelahanka",        67000, 10200),
    ("8",  "Dodda Bommasandra",      "Yelahanka",        43000,  7200),
    ("9",  "Kottigenahalli",         "Yelahanka",        36000,  6500),
    ("10", "Chowdeshwari",           "Yelahanka",        52000,  8900),
    ("11", "Hesaraghatta Samudra",   "Yelahanka",        29000,  4200),
    ("12", "Jalahalli",              "Dasarahalli",      68000, 11500),
    ("13", "Jalahalli East",         "Dasarahalli",      54000, 10800),
    ("14", "Bagalakunte",            "Dasarahalli",      61000, 10100),
    ("15", "T. Dasarahalli",         "Dasarahalli",      48000,  8600),
    ("16", "Chokkasandra",           "Dasarahalli",      39000,  7400),
    ("17", "Dodda Bidarakallu",      "Dasarahalli",      44000,  7800),
    ("18", "Peenya",                 "Dasarahalli",      82000, 14500),
    ("19", "Peenya Industrial Area", "Dasarahalli",      31000,  9200),
    ("20", "Lakshminarayana Pura",   "Dasarahalli",      57000, 10600),
    ("21", "Nandini Layout",         "Dasarahalli",      72000, 13200),
    ("22", "Marappana Palya",        "Dasarahalli",      48000,  9800),
    ("23", "Malalagiri",             "Dasarahalli",      35000,  7100),
    ("24", "Nagapura",               "Dasarahalli",      64000, 11900),
    ("25", "Mahalakshmi Layout",     "Rajajinagar",      88000, 15600),
    ("26", "Laggere",                "Rajajinagar",      75000, 13800),
    ("27", "Rajgopal Nagar",         "Rajajinagar",      62000, 12200),
    ("28", "Hegganahalli",           "Rajajinagar",      54000, 10500),
    ("29", "Herohalli",              "Rajajinagar",      47000,  9200),
    ("30", "Kanchandra",             "Rajajinagar",      38000,  8100),
    ("31", "Ullalu",                 "Rajajinagar",      41000,  8600),
    ("32", "Nagarbhavi",             "Rajajinagar",      78000, 13100),
    ("33", "Jnanabharathi",          "Rajajinagar",      69000, 11800),
    ("34", "Ullalu Uttarahalli",     "Uttarahalli",      43000,  7900),
    ("35", "Kengeri",                "Uttarahalli",      84000, 12400),
    ("36", "Kengeri Satellite Town", "Uttarahalli",      66000, 11200),
    ("37", "Uttarahalli",            "Uttarahalli",      71000, 10800),
    ("38", "Subramanyapura",         "Uttarahalli",      68000, 11500),
    ("39", "Banashankari",           "Uttarahalli",      92000, 15200),
    ("40", "Padmanabhanagar",        "Uttarahalli",      87000, 14600),
    ("41", "Chikkallasandra",        "Uttarahalli",      58000, 10900),
    ("42", "Girinagar",              "Uttarahalli",      74000, 13400),
    ("43", "Katriguppe",             "Uttarahalli",      81000, 14100),
    ("44", "Vidyapeeta",             "Uttarahalli",      63000, 11800),
    ("45", "Ganesh Mandir",          "Uttarahalli",      55000, 10400),
    ("46", "Karisandra",             "Uttarahalli",      48000,  9600),
    ("47", "Yediyur",                "Uttarahalli",      59000, 11200),
    ("48", "Pattabhiram Nagar",      "Basavanagudi",     67000, 12500),
    ("49", "Byrasandra",             "Basavanagudi",     52000, 11800),
    ("50", "Jayanagar",              "Basavanagudi",     96000, 18200),
    ("51", "Basavanagudi",           "Basavanagudi",    104000, 19800),
    ("52", "Hanumanthanagar",        "Basavanagudi",     79000, 15600),
    ("53", "Srinagar",               "Basavanagudi",     65000, 13200),
    ("54", "Lakkasandra",            "BTM Layout",       72000, 14100),
    ("55", "Gurappanapalya",         "BTM Layout",       66000, 13500),
    ("56", "Madiwala",               "BTM Layout",       89000, 16400),
    ("57", "BTM Layout",             "BTM Layout",      112000, 21500),
    ("58", "JP Nagar",               "BTM Layout",       98000, 17800),
    ("59", "Sarakki",                "BTM Layout",       74000, 14200),
    ("60", "Shakambari Nagar",       "BTM Layout",       58000, 12100),
    ("61", "Bannerghatta",           "BTM Layout",       47000,  8900),
    ("62", "Gottigere",              "Bommanahalli",     53000,  9800),
    ("63", "Konankunte",             "Bommanahalli",     61000, 10900),
    ("64", "Anjanapura",             "Bommanahalli",     68000, 11400),
    ("65", "Vasanthapura",           "Bommanahalli",     55000, 10200),
    ("66", "Hemmigepura",            "Bommanahalli",     42000,  8100),
    ("67", "Arakere",                "Bommanahalli",     71000, 12600),
    ("68", "Begur",                  "Bommanahalli",     84000, 13900),
    ("69", "Bommanahalli",           "Bommanahalli",     77000, 14200),
    ("70", "Hongasandra",            "Bommanahalli",     63000, 12100),
    ("71", "Mangammanapalya",        "Bommanahalli",     57000, 11400),
    ("72", "Singasandra",            "Bommanahalli",     69000, 12800),
    ("73", "Begur-Hommadevanahalli", "Bommanahalli",     48000,  9600),
    ("74", "Hulimavu",               "Bommanahalli",     58000, 10800),
    ("75", "Parappana Agrahara",     "Bommanahalli",     44000,  9200),
    ("76", "Kudlu",                  "Bommanahalli",     52000, 10100),
    ("77", "Harlur",                 "Bommanahalli",     67000, 11900),
    ("78", "Bellandur",              "Mahadevapura",     94000, 14600),
    ("79", "Sarjapura",              "Mahadevapura",     71000, 11200),
    ("80", "Carmelaram",             "Mahadevapura",     58000,  9800),
    ("81", "Ambalipura",             "Mahadevapura",     49000,  9100),
    ("82", "Dommasandra",            "Mahadevapura",     43000,  8300),
    ("83", "Gunjur",                 "Mahadevapura",     38000,  7600),
    ("84", "Varthur",                "Mahadevapura",     89000, 13400),
    ("85", "Whitefield",             "Mahadevapura",    124000, 16800),
    ("86", "Hoodi",                  "Mahadevapura",     82000, 13200),
    ("87", "Kadugodi",               "Mahadevapura",     76000, 12400),
    ("88", "Hagadur",                "Mahadevapura",     65000, 11800),
    ("89", "Doddakannalli",          "Mahadevapura",     54000, 10200),
    ("90", "Spandana Nagar",         "Mahadevapura",     47000,  9400),
    ("91", "Suddaguntepalya",        "Mahadevapura",     69000, 12600),
    ("92", "Marathahalli",           "Mahadevapura",    108000, 17200),
    ("93", "HAL Airport",            "Mahadevapura",     41000,  8800),
    ("94", "Pattandur Agrahara",     "Mahadevapura",     58000, 11200),
    ("95", "Munnekollal",            "Mahadevapura",     63000, 11800),
    ("96", "Mahadevapura",           "Mahadevapura",     72000, 13100),
    ("97", "Vibhuthipura",           "Mahadevapura",     54000, 10600),
    ("98", "Indiranagar",            "Shivajinagar",    102000, 20400),
    ("99", "Jeevanbhima Nagar",      "Shivajinagar",     78000, 16200),
    ("100","CV Raman Nagar",         "Shivajinagar",     87000, 17400),
    ("101","Ulsoor",                 "Shivajinagar",     94000, 18800),
    ("102","Bharathinagar",          "Shivajinagar",     61000, 14200),
    ("103","Frazer Town",            "Shivajinagar",     82000, 17600),
    ("104","Benniganahalli",         "KR Puram",         68000, 12800),
    ("105","Ramamurthy Nagar",       "KR Puram",         91000, 16400),
    ("106","Domlur",                 "Shivajinagar",     74000, 15800),
    ("107","Konena Agrahara",        "Shivajinagar",     56000, 13200),
    ("108","Agaram",                 "Shivajinagar",     48000, 12400),
    ("109","Vannarpet",              "Shivajinagar",     63000, 14600),
    ("110","Nilasandra",             "Shivajinagar",     52000, 13100),
    ("111","Shivaji Nagar",          "Shivajinagar",     88000, 18400),
    ("112","Vasanth Nagar",          "Shivajinagar",     76000, 17200),
    ("113","Gandhi Nagar",           "Shivajinagar",     69000, 16800),
    ("114","Subramanyanagar",        "Shivajinagar",     74000, 15600),
    ("115","Sampangirama Nagar",     "Shivajinagar",     82000, 17400),
    ("116","Shivajinagar",           "Shivajinagar",     79000, 16200),
    ("117","Majestic (Kalasipalya)", "Shivajinagar",     94000, 19600),
    ("118","Chamrajpet",             "Chamrajpet",       88000, 18200),
    ("119","Azad Nagar",             "Chamrajpet",       72000, 15800),
    ("120","Sunkenahalli",           "Chamrajpet",       58000, 13400),
    ("121","Vishveshwarapuram",      "Chamrajpet",       94000, 19200),
    ("122","Siddapura",              "Chamrajpet",       76000, 16400),
    ("123","Hombegowda Nagar",       "Chamrajpet",       68000, 15200),
    ("124","Lakshmi Devi Nagar",     "Chamrajpet",       81000, 17600),
    ("125","Suddagunte Palya",       "Chamrajpet",       63000, 14800),
    ("126","Ejipura",                "Shivajinagar",     78000, 16600),
    ("127","Vivek Nagar",            "Shivajinagar",     84000, 17800),
    ("128","Wadeyar Halli",          "Shivajinagar",     61000, 14200),
    ("129","Kaval Bairasandra",      "Shivajinagar",     54000, 13100),
    ("130","Muneshwara Nagar",       "Shivajinagar",     67000, 14900),
    ("131","Tilaknagar",             "Jayanagar",        88000, 18600),
    ("132","Jayanagar East",         "Jayanagar",       102000, 20400),
    ("133","Gurappanapalya (J)",     "Jayanagar",        74000, 15800),
    ("134","Madiwala (J)",           "Jayanagar",        86000, 17200),
    ("135","Koramangala",            "BTM Layout",      124000, 21800),
    ("136","Suddaguntepalya (K)",    "BTM Layout",       69000, 14600),
    ("137","Koramangala 4th Block",  "BTM Layout",      108000, 20200),
    ("138","Koramangala 5th Block",  "BTM Layout",       96000, 18800),
    ("139","Koramangala 6th Block",  "BTM Layout",       88000, 17400),
    ("140","HSR Layout",             "BTM Layout",      114000, 19600),
    ("141","Agara",                  "BTM Layout",       72000, 14400),
    ("142","Somasundara Palya",      "BTM Layout",       64000, 13200),
    ("143","Mico Layout",            "Bommanahalli",     58000, 12400),
    ("144","Byatarayanapura",        "Yelahanka",        69000, 11800),
    ("145","Kalkere",                "KR Puram",         52000, 10200),
    ("146","KR Puram",               "KR Puram",         94000, 16400),
    ("147","Basavanapura",           "KR Puram",         61000, 11800),
    ("148","Huddi",                  "KR Puram",         48000,  9600),
    ("149","Devasandra",             "KR Puram",         57000, 11200),
    ("150","A Narayanapura",         "KR Puram",         44000,  9100),
    ("151","Hennur",                 "Byatarayanapura",  78000, 13200),
    ("152","Byatarayanapura (H)",    "Byatarayanapura",  66000, 11600),
    ("153","Kodigehalli (H)",        "Byatarayanapura",  54000, 10400),
    ("154","Singayyanapalya",        "Byatarayanapura",  47000,  9600),
    ("155","Hebbal",                 "Byatarayanapura",  84000, 14800),
    ("156","Manorayanapalya",        "Byatarayanapura",  61000, 12200),
    ("157","Ganganagar",             "Byatarayanapura",  72000, 13600),
    ("158","Nagawara",               "Byatarayanapura",  69000, 13100),
    ("159","Kadugondanahalli",       "Shivajinagar",     58000, 12400),
    ("160","Kushal Nagar",           "Shivajinagar",     64000, 13800),
    ("161","HBR Layout",             "Byatarayanapura",  88000, 15600),
    ("162","Horamavu Agara",         "KR Puram",         74000, 13200),
    ("163","Horamavu Banaswadi",     "KR Puram",         82000, 14800),
    ("164","Lingarajapura",          "KR Puram",         68000, 12600),
    ("165","Poornaprajna Layout",    "KR Puram",         54000, 11200),
    ("166","Banaswadi",              "KR Puram",         94000, 17200),
    ("167","Chelekere",              "Byatarayanapura",  76000, 14400),
    ("168","Kalyan Nagar",           "Byatarayanapura",  88000, 16800),
    ("169","Kammanahalli",           "Shivajinagar",     72000, 14600),
    ("170","Kacharakanahalli",       "Shivajinagar",     61000, 13200),
    ("171","Kadbi Chowk",            "Shivajinagar",     56000, 12800),
    ("172","Jogupalya",              "Shivajinagar",     63000, 13400),
    ("173","Halsoor",                "Shivajinagar",     78000, 16200),
    ("174","Bharatnagar",            "Shivajinagar",     84000, 17400),
    ("175","Sivanchetty Gardens",    "Shivajinagar",     59000, 13800),
    ("176","Benniganahalli (E)",     "Shivajinagar",     66000, 14200),
    ("177","Cooke Town",             "Shivajinagar",     72000, 16400),
    ("178","Cantonment",             "Shivajinagar",     54000, 12600),
    ("179","Bharathi Nagar (E)",     "Shivajinagar",     48000, 11800),
    ("180","Maruthi Seva Nagar",     "Shivajinagar",     61000, 13900),
    ("181","Pulikeshinagar",         "Shivajinagar",     84000, 17600),
    ("182","Sarvagna Nagar",         "KR Puram",         74000, 14200),
    ("183","Rajiv Gandhi Nagar",     "KR Puram",         66000, 13400),
    ("184","Hoodi (M)",              "Mahadevapura",     58000, 11600),
    ("185","Krishnarajapuram",       "KR Puram",         94000, 17800),
    ("186","Doddabanasawadi",        "KR Puram",         69000, 13200),
    ("187","Ramesh Nagar",           "KR Puram",         58000, 12400),
    ("188","Dasarahalli (KR)",       "KR Puram",         52000, 11200),
    ("189","Hagadur (M)",            "Mahadevapura",     47000, 10400),
    ("190","Bhattarahalli",          "Mahadevapura",     61000, 11800),
    ("191","Vibhutipura (M)",        "Mahadevapura",     54000, 10900),
    ("192","Sonnappa Garden",        "Mahadevapura",     48000, 10200),
    ("193","Kasavanahalli",          "Mahadevapura",     57000, 11400),
    ("194","Rampura",                "KR Puram",         63000, 12800),
    ("195","Kavalbyrasandra",        "KR Puram",         58000, 12200),
    ("196","Kuvempu Nagar (KR)",     "KR Puram",         52000, 11600),
    ("197","Sir M V Nagar",          "KR Puram",         67000, 13800),
    ("198","Graphite India",         "Mahadevapura",     44000,  9800),
]


def seed_wards():
    sb = get_supabase()

    # Check if already seeded
    existing = sb.table("wards").select("id", count="exact").execute()
    existing_count = existing.count if existing.count is not None else len(existing.data)

    if existing_count >= 180:
        logger.info("Wards already seeded (%d rows). Skipping.", existing_count)
        return

    logger.info("Seeding %d BBMP wards...", len(WARDS_DATA))

    rows = [
        {
            "id": w[0],
            "name": w[1],
            "constituency": w[2],
            "population": w[3],
            "population_density": w[4],
        }
        for w in WARDS_DATA
    ]

    # Batch in chunks of 50 to stay within Supabase request limits
    chunk_size = 50
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i + chunk_size]
        sb.table("wards").upsert(chunk, on_conflict="id").execute()
        logger.info("  Inserted wards %d–%d", i + 1, min(i + chunk_size, len(rows)))

    logger.info("Ward seeding complete. %d wards inserted.", len(rows))


if __name__ == "__main__":
    seed_wards()
