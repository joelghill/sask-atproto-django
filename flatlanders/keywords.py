"""Module containing keywords for the Flatlanders algorithm."""

import re

SASK_WORDS = {
    "sask",
    "saskatchewan",
    "saskatoon",
    "saskatchatoon",
    "saskatchewanians",
    "saskatchewanian",
    "city of regina",
    "regina, sk",
    "regina, sask",
    "regina sask",
    "regina sk",
    " yxe ",
    " yxecc ",
    " yqr ",
    " yqrcc ",
    " skpoli ",
    "#yxe",
    "#yxecc",
    "#yqr",
    "#yqrcc",
    "#skpoli",
    "land of the living skies",
}


POLITICAL_WORDS = {
    "legislature",
    "legislative",
    "legislative assembly",
    "mla",
    "mlas",
    "member of the legislative assembly",
    "premier",
    "premiers",
    "prime minister",
    "prime ministers",
    "minister",
    "ministers",
    "cabinet",
    "cabinet minister",
    "cabinet ministers",
    "opposition",
    "opposition leader",
    "opposition leaders",
    "opposition party",
    "opposition parties",
    "government",
    "governments",
    "government leader",
    "government leaders",
    "house of commons",
    "house leader",
    "skpoli",
    "skpolitics",
    "politics",
    "political",
    "political party",
    "political parties",
    "election",
    "elections",
    "sask party",
    "ndp",
    "sask ndp",
    "new democratic party",
    "progressive conservative",
    "saskatchewan party",
    "saskatchewan ndp",
    "saskatchewan progressive conservative",
    "sask united party",
    "saskatchewan green party",
}


SASK_POLITICIANS = {
    "Ryan Domotor",
    "Greg Lawrence",
    "Nadine Wilson",
    "carla beck",
    "jennifer bowes",
    "Noor Burki",
    "Jared Clarke",
    "Meara Conway",
    "Matt Love",
    "Vicki Mowat",
    "Betty Nippi-Albright",
    "Betty Nippi",
    "Erika Ritchie",
    "Nicole Sarauer",
    "Nathaniel Teed",
    "Doyle Vermette",
    "Trent Wotherspoon",
    "Aleana Young",
    "Steven Bonk",
    "Terry Dennis",
    "Dustion Duncan",
    "Hugh Nerlien",
    "Don Morgan",
    "Jeremy Harrison",
    "Paul Merriman",
    "Jim Reiter",
    "Ken Cheveldayoff",
    "Greg Ottenbreit",
    "Joe Hargrave",
    "Bronwyn Eyre",
    "David Buckingham",
    "Gene Makowsky",
    "Laura Ross",
    "Fred Bradshaw",
    "Everett Hindley",
    "Warren Kaeding",
    "Lori Carr",
    "Muhammad Fiaz",
    "Eric Olauson",
    "Ken Francis",
    "Lisa Lambert",
    "Mark Docherty",
    "Marv Friesen",
    "Todd Goudy",
    "Gary Grewal",
    "Donna Harpauer",
    "Scott Moe",
    "Daryl Harrison",
    "Terry Jenson",
    "Travel Kuzminski",
    "Delbert Kirsch",
    "Jim Lemaigre",
    "David Marit",
    "Blaine McLeod",
    "Tim McLeod",
    "Don McMorris",
    "Alana Ross",
    "Dana Skoropad",
    "Doug Steele",
    "Christine Tell",
    "Randy Weekes",
    "Gordon Wyant",
    "Colleen Young",
    "premier moe"
}

MUTED_WORDS = [
    "elon",
    "musk",
    "#abpoli",
    "#cdnpoli",
    "#abpoli",
    "#onpoli",
    "#pqpoli",
    "#bcpoli",
    "#mbpoli",
    "#pepoli", 
    "#nspoli", 
    "#nbpoli", 
    "#nlpoli", 
    "#nupoli", 
    "#ntpoli", 
    "#ytpoli",
    "#elxn2025",
    "#canada"
]


POLITICAL_CONTENT = POLITICAL_WORDS.union(SASK_POLITICIANS)

SASK_CONTENT = SASK_WORDS.union(SASK_POLITICIANS)

COMPILED_PATTERNS = [re.compile(rf"\b{word.lower()}\b") for word in SASK_CONTENT]

COMPILED_MUTE_PATTERNS = [re.compile(rf"\b{word.lower()}\b") for word in MUTED_WORDS]


def is_sask_text(text: str) -> bool:
    """Check if a text contains any of the Saskatchewan keywords"""
    lower_text = text.lower()
    return any(pattern.search(lower_text) for pattern in COMPILED_PATTERNS)

def is_muted(text: str) -> bool:
    """Check if a text contains any of the muted keywords"""
    lower_text = text.lower()
    return any(pattern.search(lower_text) for pattern in COMPILED_MUTE_PATTERNS)
