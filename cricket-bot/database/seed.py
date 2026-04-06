"""Database seed script – imports players from real_players.json."""

import json
import logging
import os

from config.database import SessionLocal, init_db
from database.crud import bulk_create_players, get_player_count

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "data")
PLAYERS_FILE = os.path.join(DATA_DIR, "real_players.json")


def seed_database():
    """Initialize database tables and seed player data."""
    logger.info("Initializing database tables...")
    init_db()

    db = SessionLocal()
    try:
        existing = get_player_count(db)
        if existing > 0:
            logger.info("Database already has %d players. Skipping seed.", existing)
            return existing

        if not os.path.exists(PLAYERS_FILE):
            logger.warning("Player data file not found: %s", PLAYERS_FILE)
            logger.info("Generating player data...")
            _generate_player_data()

        logger.info("Loading players from %s...", PLAYERS_FILE)
        with open(PLAYERS_FILE, "r", encoding="utf-8") as f:
            players_data = json.load(f)

        logger.info("Loaded %d players from JSON", len(players_data))
        count = bulk_create_players(db, players_data)
        logger.info("Seeded %d players into database", count)
        return count
    finally:
        db.close()


def _generate_player_data():
    """Generate real_players.json with 3200 cricket players using realistic data."""
    import random

    random.seed(42)

    # Real cricket player names organized by country
    players_by_country = _get_player_database()

    all_players = []
    player_names_seen = set()

    for country, names in players_by_country.items():
        for name in names:
            if name in player_names_seen:
                continue
            player_names_seen.add(name)

            rating = random.randint(50, 100)
            category = random.choice(["Batsman", "Bowler", "All-rounder", "Wicket Keeper"])
            bat_hand = random.choice(["Right", "Left"])
            bowl_hand = random.choice(["Right", "Left"])
            bowl_style = random.choice(["Fast", "Off Spinner", "Leg Spinner", "Medium Pacer"])

            # Generate realistic stats based on rating and category
            bat_rating = _generate_bat_rating(rating, category)
            bowl_rating = _generate_bowl_rating(rating, category)
            bat_avg = round(random.uniform(15.0, 60.0) * (rating / 80), 1)
            sr = round(random.uniform(60.0, 180.0) * (rating / 85), 1)
            runs = int(random.uniform(100, 15000) * (rating / 75))
            centuries_val = max(0, int(runs / random.uniform(800, 2000)))
            bowl_avg_val = round(random.uniform(18.0, 50.0) * (80 / max(rating, 50)), 1)
            economy_val = round(random.uniform(3.0, 10.0) * (75 / max(rating, 50)), 1)
            wickets_val = int(random.uniform(0, 500) * (rating / 75))

            all_players.append({
                "name": name,
                "version": "Base",
                "rating": rating,
                "category": category,
                "country": country,
                "bat_hand": bat_hand,
                "bowl_hand": bowl_hand,
                "bowl_style": bowl_style,
                "bat_rating": bat_rating,
                "bowl_rating": bowl_rating,
                "bat_avg": bat_avg,
                "strike_rate": sr,
                "runs": runs,
                "centuries": centuries_val,
                "bowl_avg": bowl_avg_val,
                "economy": economy_val,
                "wickets": wickets_val,
                "is_active": True,
                "image_url": None,
            })

    # Pad to 3200 if needed with generated names
    while len(all_players) < 3200:
        idx = len(all_players) + 1
        country = random.choice(list(players_by_country.keys()))
        name = f"Player {idx} ({country})"
        if name in player_names_seen:
            continue
        player_names_seen.add(name)

        rating = random.randint(50, 85)
        category = random.choice(["Batsman", "Bowler", "All-rounder", "Wicket Keeper"])
        bat_hand = random.choice(["Right", "Left"])
        bowl_hand = random.choice(["Right", "Left"])
        bowl_style = random.choice(["Fast", "Off Spinner", "Leg Spinner", "Medium Pacer"])

        all_players.append({
            "name": name,
            "version": "Base",
            "rating": rating,
            "category": category,
            "country": country,
            "bat_hand": bat_hand,
            "bowl_hand": bowl_hand,
            "bowl_style": bowl_style,
            "bat_rating": _generate_bat_rating(rating, category),
            "bowl_rating": _generate_bowl_rating(rating, category),
            "bat_avg": round(random.uniform(15.0, 50.0) * (rating / 80), 1),
            "strike_rate": round(random.uniform(60.0, 150.0) * (rating / 85), 1),
            "runs": int(random.uniform(100, 8000) * (rating / 75)),
            "centuries": max(0, random.randint(0, rating // 10)),
            "bowl_avg": round(random.uniform(20.0, 45.0) * (80 / max(rating, 50)), 1),
            "economy": round(random.uniform(3.5, 9.0) * (75 / max(rating, 50)), 1),
            "wickets": int(random.uniform(0, 300) * (rating / 75)),
            "is_active": True,
            "image_url": None,
        })

    # Truncate to 3200
    all_players = all_players[:3200]

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PLAYERS_FILE, "w", encoding="utf-8") as f:
        json.dump(all_players, f, indent=2, ensure_ascii=False)

    logger.info("Generated %d players and saved to %s", len(all_players), PLAYERS_FILE)


def _generate_bat_rating(overall: int, category: str) -> int:
    """Generate batting rating based on overall rating and category."""
    import random
    if category in ("Batsman", "Wicket Keeper"):
        return min(100, max(50, overall + random.randint(-5, 5)))
    elif category == "All-rounder":
        return min(100, max(50, overall + random.randint(-10, 3)))
    else:
        return min(100, max(50, overall - random.randint(5, 20)))


def _generate_bowl_rating(overall: int, category: str) -> int:
    """Generate bowling rating based on overall rating and category."""
    import random
    if category == "Bowler":
        return min(100, max(50, overall + random.randint(-5, 5)))
    elif category == "All-rounder":
        return min(100, max(50, overall + random.randint(-10, 3)))
    else:
        return min(100, max(50, overall - random.randint(5, 20)))


def _get_player_database() -> dict[str, list[str]]:
    """Return a dictionary of country -> list of player names."""
    return {
        "India": [
            "Virat Kohli", "Rohit Sharma", "Jasprit Bumrah", "MS Dhoni", "Hardik Pandya",
            "Ravindra Jadeja", "Rishabh Pant", "KL Rahul", "Shubman Gill", "Suryakumar Yadav",
            "Mohammed Shami", "Kuldeep Yadav", "Axar Patel", "Shreyas Iyer", "Ishan Kishan",
            "Ravichandran Ashwin", "Bhuvneshwar Kumar", "Yuzvendra Chahal", "Washington Sundar",
            "Shardul Thakur", "Deepak Chahar", "Prithvi Shaw", "Ruturaj Gaikwad",
            "Sanju Samson", "Abhishek Sharma", "Tilak Varma", "Nitish Kumar Reddy",
            "Rinku Singh", "Shivam Dube", "Arshdeep Singh", "Mohammed Siraj", "Umran Malik",
            "Ravi Bishnoi", "Krunal Pandya", "Deepak Hooda", "Harshal Patel",
            "Devdutt Padikkal", "Yashasvi Jaiswal", "Sarfaraz Khan", "Rajat Patidar",
            "Dhruv Jurel", "Mukesh Kumar", "Prasidh Krishna", "Avesh Khan",
            "T Natarajan", "Rahul Tewatia", "Varun Chakaravarthy", "Tushar Deshpande",
            "Ramandeep Singh", "Sai Sudharsan", "Riyan Parag", "Harshit Rana",
            "Mayank Yadav", "Yash Dayal", "Akash Deep", "Jitesh Sharma",
            "Manish Pandey", "Ambati Rayudu", "Cheteshwar Pujara", "Ajinkya Rahane",
            "Wriddhiman Saha", "Dinesh Karthik", "Robin Uthappa", "Manoj Tiwary",
            "Suresh Raina", "Gautam Gambhir", "Virender Sehwag", "Sachin Tendulkar",
            "Rahul Dravid", "Sourav Ganguly", "VVS Laxman", "Yuvraj Singh",
            "Harbhajan Singh", "Zaheer Khan", "Irfan Pathan", "Ashish Nehra",
            "Ishant Sharma", "Umesh Yadav", "Amit Mishra", "Piyush Chawla",
            "Jaydev Unadkat", "Dhawal Kulkarni", "Manoj Prabhakar", "Javagal Srinath",
            "Anil Kumble", "Kapil Dev", "Sandeep Sharma", "Navdeep Saini",
            "Karun Nair", "Hanuma Vihari", "Mayank Agarwal", "Shikhar Dhawan",
            "Murali Vijay", "KS Bharat", "Sheldon Jackson", "Anmolpreet Singh",
            "Vivrant Sharma", "Rahul Chahar", "Ravi Ashwin", "Shahbaz Ahmed",
            "Venkatesh Iyer", "Ayush Badoni", "Yash Dhull", "Priyam Garg",
            "Abdul Samad", "Kartik Tyagi", "Mavi Kumar", "Mohsin Khan",
            "Ankit Rajpoot", "Deepak Shodhan", "Lalit Yadav", "Chetan Sakariya",
            "Basil Thampi", "Sandeep Warrier", "Varun Aaron", "Khaleel Ahmed",
            "Parvez Rasool", "Shahbaz Nadeem", "Saurabh Kumar", "Akash Madhwal",
            "Naman Dhir", "Harpreet Brar", "Arshad Khan", "Atharva Taide",
            "Swapnil Singh", "Himanshu Sharma", "Aman Hakim Khan",
        ],
        "Australia": [
            "Pat Cummins", "Steve Smith", "David Warner", "Mitchell Starc", "Josh Hazlewood",
            "Travis Head", "Marnus Labuschagne", "Glenn Maxwell", "Nathan Lyon", "Alex Carey",
            "Adam Zampa", "Mitchell Marsh", "Marcus Stoinis", "Aaron Finch", "Cameron Green",
            "Matthew Wade", "Usman Khawaja", "Scott Boland", "Sean Abbott", "Jhye Richardson",
            "Tim David", "Ashton Agar", "Daniel Sams", "Josh Inglis", "Spencer Johnson",
            "Jake Fraser-McGurk", "Matt Short", "Ben McDermott", "Mitch Swepson",
            "Michael Neser", "Riley Meredith", "Kane Richardson", "Jason Behrendorff",
            "Moises Henriques", "D'Arcy Short", "Chris Lynn", "Ben Cutting", "Andrew Tye",
            "Billy Stanlake", "Mark Steketee", "James Pattinson", "Peter Siddle",
            "Shaun Marsh", "George Bailey", "Brad Hodge", "Mike Hussey",
            "Ricky Ponting", "Adam Gilchrist", "Shane Warne", "Brett Lee",
            "Glenn McGrath", "Justin Langer", "Matthew Hayden", "Jason Gillespie",
            "Brad Hogg", "Michael Clarke", "James Faulkner", "Clint McKay",
            "Peter Handscomb", "Will Pucovski", "Sam Konstas", "Beau Webster",
            "Todd Murphy", "Lance Morris", "Xavier Bartlett", "Nathan Ellis",
            "Tanveer Sangha", "Matthew Kuhnemann", "Josh Philippe", "Hayden Kerr",
            "Ben Dwarshuis", "Wes Agar", "Jack Wildermuth", "Michael Neser",
        ],
        "England": [
            "Jos Buttler", "Ben Stokes", "Joe Root", "Jofra Archer", "Mark Wood",
            "Jonny Bairstow", "Harry Brook", "Liam Livingstone", "Moeen Ali", "Chris Woakes",
            "Sam Curran", "Adil Rashid", "Reece Topley", "Tom Hartley", "Phil Salt",
            "Zak Crawley", "Ollie Pope", "Ben Duckett", "Jamie Smith", "Gus Atkinson",
            "Chris Jordan", "David Willey", "Jason Roy", "Alex Hales", "Dawid Malan",
            "Tom Curran", "Tymal Mills", "Saqib Mahmood", "Matt Parkinson",
            "Will Jacks", "Jamie Overton", "Olly Stone", "Craig Overton",
            "Dom Bess", "Jack Leach", "Stuart Broad", "James Anderson",
            "Eoin Morgan", "Kevin Pietersen", "Andrew Flintoff", "Alastair Cook",
            "Ian Bell", "Graeme Swann", "Tim Bresnan", "Steven Finn",
            "Shoaib Bashir", "Brydon Carse", "Matthew Potts", "Ollie Robinson",
            "Dan Lawrence", "Sam Billings", "Liam Dawson", "Lewis Gregory",
            "Tom Abell", "Luke Wood", "Richard Gleeson", "George Garton",
            "Jordan Cox", "Jacob Bethell", "Josh Tongue", "Matthew Fisher",
        ],
        "South Africa": [
            "Quinton de Kock", "Kagiso Rabada", "Anrich Nortje", "David Miller",
            "Aiden Markram", "Rassie van der Dussen", "Marco Jansen", "Lungi Ngidi",
            "Tabraiz Shamsi", "Keshav Maharaj", "Heinrich Klaasen", "Faf du Plessis",
            "Temba Bavuma", "Reeza Hendricks", "Wayne Parnell", "Dwaine Pretorius",
            "Tristan Stubbs", "Gerald Coetzee", "Lizaad Williams", "Sisanda Magala",
            "Ryan Rickelton", "Tony de Zorzi", "Wiaan Mulder", "Kyle Verreynne",
            "Dewald Brevis", "Bjorn Fortuin", "George Linde", "Junior Dala",
            "Ottniel Baartman", "Nandre Burger", "Dale Steyn", "AB de Villiers",
            "Hashim Amla", "Jacques Kallis", "Graeme Smith", "Mark Boucher",
            "Morne Morkel", "Vernon Philander", "Imran Tahir", "JP Duminy",
            "Dean Elgar", "Sarel Erwee", "Keegan Petersen", "Zubayr Hamza",
            "Simon Harmer", "Dane Paterson", "Beuran Hendricks", "Andile Phehlukwayo",
            "Chris Morris", "Robbie Frylinck", "Marchant de Lange", "Corbin Bosch",
        ],
        "New Zealand": [
            "Kane Williamson", "Trent Boult", "Tim Southee", "Devon Conway",
            "Glenn Phillips", "Daryl Mitchell", "Kyle Jamieson", "Mitchell Santner",
            "Matt Henry", "Tom Latham", "Lockie Ferguson", "Ish Sodhi",
            "Adam Milne", "Mark Chapman", "James Neesham", "Michael Bracewell",
            "Rachin Ravindra", "Will Young", "Finn Allen", "Ben Sears",
            "Josh Clarkson", "Henry Nicholls", "Ross Taylor", "Martin Guptill",
            "Brendon McCullum", "Daniel Vettori", "Nathan Astle", "Chris Cairns",
            "Shane Bond", "Jacob Duffy", "Blair Tickner", "Scott Kuggeleijn",
            "Colin Munro", "Tom Blundell", "Cole McConchie", "Doug Bracewell",
            "Ajaz Patel", "Will Somerville", "Neil Wagner", "Colin de Grandhomme",
        ],
        "Pakistan": [
            "Babar Azam", "Shaheen Shah Afridi", "Naseem Shah", "Mohammad Rizwan",
            "Fakhar Zaman", "Shadab Khan", "Haris Rauf", "Iftikhar Ahmed",
            "Mohammad Nawaz", "Usama Mir", "Saim Ayub", "Abdullah Shafique",
            "Imam-ul-Haq", "Saud Shakeel", "Mohammad Abbas", "Hasan Ali",
            "Faheem Ashraf", "Khushdil Shah", "Asif Ali", "Mohammad Hasnain",
            "Abrar Ahmed", "Noman Ali", "Salman Ali Agha", "Mir Hamza",
            "Zaman Khan", "Abbas Afridi", "Azam Khan", "Sharjeel Khan",
            "Ahmed Shehzad", "Umar Akmal", "Shoaib Malik", "Mohammad Hafeez",
            "Wahab Riaz", "Junaid Khan", "Yasir Shah", "Sarfaraz Ahmed",
            "Mohammad Amir", "Imad Wasim", "Rumman Raees", "Haris Sohail",
            "Shan Masood", "Kamran Ghulam", "Tayyab Tahir", "Muhammad Irfan Khan",
        ],
        "West Indies": [
            "Nicholas Pooran", "Shai Hope", "Alzarri Joseph", "Gudakesh Motie",
            "Shimron Hetmyer", "Brandon King", "Jason Holder", "Roston Chase",
            "Akeal Hosein", "Kyle Mayers", "Romario Shepherd", "Keacy Carty",
            "Rovman Powell", "Obed McCoy", "Jayden Seales", "Kemar Roach",
            "Shannon Gabriel", "Andre Russell", "Sunil Narine", "Kieron Pollard",
            "Chris Gayle", "Brian Lara", "Curtly Ambrose", "Courtney Walsh",
            "Dwayne Bravo", "DJ Bravo", "Darren Sammy", "Samuel Badree",
            "Lendl Simmons", "Evin Lewis", "Fabian Allen", "Sheldon Cottrell",
            "Oshane Thomas", "Odean Smith", "Rahkeem Cornwall", "Kraigg Brathwaite",
            "Jermaine Blackwood", "Joshua Da Silva", "Matthew Forde", "Shamar Joseph",
        ],
        "Sri Lanka": [
            "Wanindu Hasaranga", "Pathum Nissanka", "Charith Asalanka", "Kusal Mendis",
            "Dhananjaya de Silva", "Maheesh Theekshana", "Dunith Wellalage",
            "Kusal Perera", "Dasun Shanaka", "Chamika Karunaratne", "Dushmantha Chameera",
            "Lahiru Kumara", "Dilshan Madushanka", "Matheesha Pathirana",
            "Angelo Mathews", "Dinesh Chandimal", "Dimuth Karunaratne",
            "Lasith Malinga", "Muttiah Muralitharan", "Kumar Sangakkara",
            "Mahela Jayawardene", "Sanath Jayasuriya", "Aravinda de Silva",
            "Chaminda Vaas", "Rangana Herath", "Thisara Perera", "Niroshan Dickwella",
            "Avishka Fernando", "Bhanuka Rajapaksa", "Jeffrey Vandersay",
            "Binura Fernando", "Kasun Rajitha", "Vishwa Fernando", "Asitha Fernando",
            "Prabath Jayasuriya", "Ramesh Mendis", "Sadeera Samarawickrama",
        ],
        "Bangladesh": [
            "Shakib Al Hasan", "Mushfiqur Rahim", "Mustafizur Rahman", "Tamim Iqbal",
            "Liton Das", "Mehidy Hasan Miraz", "Taskin Ahmed", "Najmul Hossain Shanto",
            "Shoriful Islam", "Towhid Hridoy", "Afif Hossain", "Nasum Ahmed",
            "Tanzim Hasan Sakib", "Hasan Mahmud", "Rishad Hossain",
            "Tanzid Hasan", "Mahmudullah", "Sabbir Rahman", "Mashrafe Mortaza",
            "Rubel Hossain", "Taijul Islam", "Abu Jayed", "Mominul Haque",
            "Imrul Kayes", "Soumya Sarkar", "Khaled Ahmed", "Ebadot Hossain",
            "Nurul Hasan", "Yasir Ali", "Mahedi Hasan", "Naim Sheikh",
        ],
        "Afghanistan": [
            "Rashid Khan", "Rahmanullah Gurbaz", "Ibrahim Zadran", "Fazalhaq Farooqi",
            "Naveen-ul-Haq", "Azmatullah Omarzai", "Mohammad Nabi", "Mujeeb Ur Rahman",
            "Noor Ahmad", "Gulbadin Naib", "Najibullah Zadran", "Hashmatullah Shahidi",
            "Asghar Afghan", "Hamid Hassan", "Dawlat Zadran", "Shapoor Zadran",
            "Samiullah Shinwari", "Karim Janat", "Qais Ahmad", "Fareed Ahmad Malik",
            "Hazratullah Zazai", "Usman Ghani", "Rahmat Shah", "Darwish Rasooli",
            "AM Ghazanfar", "Allah Ghazanfar", "Sediqullah Atal",
        ],
        "Zimbabwe": [
            "Sikandar Raza", "Sean Williams", "Blessing Muzarabani", "Craig Ervine",
            "Regis Chakabva", "Richard Ngarava", "Luke Jongwe", "Ryan Burl",
            "Tendai Chatara", "Wellington Masakadza", "Wessly Madhevere",
            "Brad Evans", "Clive Madande", "Joylord Gumbie", "Victor Nyauchi",
            "Brian Chari", "Brendan Taylor", "Hamilton Masakadza", "Kyle Jarvis",
            "Graeme Cremer", "Elton Chigumbura", "Heath Streak", "Andy Flower",
            "Grant Flower", "Henry Olonga", "Tatenda Taibu",
        ],
        "Ireland": [
            "Paul Stirling", "Josh Little", "Andrew Balbirnie", "Curtis Campher",
            "Mark Adair", "Harry Tector", "Lorcan Tucker", "George Dockrell",
            "Barry McCarthy", "Craig Young", "Gareth Delany", "Simi Singh",
            "Kevin O'Brien", "Boyd Rankin", "Tim Murtagh", "William Porterfield",
            "Andy McBrine", "Graham Hume", "Ben White", "Ross Adair",
        ],
        "Scotland": [
            "Richie Berrington", "Michael Leask", "Brandon McMullen", "Mark Watt",
            "Chris Greaves", "Safyaan Sharif", "Brad Wheal", "George Munsey",
            "Kyle Coetzer", "Matthew Cross", "Calum MacLeod", "Craig Wallace",
        ],
        "Netherlands": [
            "Ryan ten Doeschate", "Roelof van der Merwe", "Paul van Meekeren",
            "Bas de Leede", "Logan van Beek", "Scott Edwards", "Max O'Dowd",
            "Teja Nidamanuru", "Tim Pringle", "Aryan Dutt", "Fred Klaassen",
            "Shane Snater", "Vikramjit Singh", "Wesley Barresi",
        ],
        "Namibia": [
            "Gerhard Erasmus", "David Wiese", "JJ Smit", "Jan Frylinck",
            "Bernard Scholtz", "Ruben Trumpelmann", "Zane Green", "Stephan Baard",
            "Michael van Lingen", "Niko Davin", "Tangeni Lungameni", "Ben Shikongo",
        ],
        "Nepal": [
            "Sandeep Lamichhane", "Kushal Bhurtel", "Dipendra Singh Airee",
            "Rohit Paudel", "Sompal Kami", "Aasif Sheikh", "Karan KC",
            "Gulshan Jha", "Paras Khadka", "Lalit Rajbanshi", "Abinash Bohara",
        ],
        "Oman": [
            "Aqib Ilyas", "Zeeshan Maqsood", "Bilal Khan", "Mehran Khan",
            "Ayaan Khan", "Kashyap Prajapati", "Pratik Athavale", "Naseem Khushi",
            "Kaleemullah", "Fayyaz Butt", "Sufyan Mehmood",
        ],
        "USA": [
            "Aaron Jones", "Saurabh Netravalkar", "Ali Khan", "Monank Patel",
            "Steven Taylor", "Corey Anderson", "Rusty Theron", "Nosthush Kenjige",
            "Jasdeep Singh", "Harmeet Singh", "Andries Gous", "Milind Kumar",
        ],
        "Canada": [
            "Navneet Dhaliwal", "Saad Bin Zafar", "Dilpreet Bajwa", "Ravinderpal Singh",
            "Kaleem Sana", "Jeremy Gordon", "Aaron Johnson", "Shreyas Movva",
            "Pargat Singh", "Junaid Siddiqui", "Nicholas Kirton",
        ],
        "UAE": [
            "Muhammad Waseem", "Vriitya Aravind", "Junaid Siddique", "Basil Hameed",
            "Zahoor Khan", "Ahmed Raza", "Rohan Mustafa", "Chirag Suri",
            "Karthik Meiyappan", "Alishan Sharafu",
        ],
        "Kenya": [
            "Collins Obuya", "Thomas Odoyo", "Steve Tikolo", "Maurice Ouma",
            "Nehemiah Odhiambo", "Seren Waters", "Jimmy Kamande", "Alex Obanda",
        ],
        "Papua New Guinea": [
            "Assad Vala", "Charles Amini", "Norman Vanua", "Lega Siaka",
            "Kabua Morea", "Sese Bau", "Tony Ura", "Kiplin Doriga",
        ],
    }
    return players_by_country


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from config.logging_config import setup_logging
    setup_logging()
    seed_database()
