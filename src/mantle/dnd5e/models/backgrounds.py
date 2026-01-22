"""D&D 5e SRD Backgrounds."""

from typing import List, Dict, Any
from pydantic import BaseModel


class BackgroundData(BaseModel):
    """Data model for character backgrounds."""
    id: str
    display_name: str
    description: str
    skill_proficiencies: List[str]  # Always 2 skills
    tool_proficiencies: List[str] = []
    languages: int = 0  # Number of languages to choose
    equipment: List[str] = []
    gold: int = 0
    feature_name: str = ""
    feature_description: str = ""
    personality_traits: List[str] = []
    ideals: List[str] = []
    bonds: List[str] = []
    flaws: List[str] = []


# SRD Backgrounds
BACKGROUNDS: Dict[str, BackgroundData] = {
    "acolyte": BackgroundData(
        id="acolyte",
        display_name="Acolyte",
        description="You have spent your life in service to a temple, learning sacred rites and providing sacrifices.",
        skill_proficiencies=["insight", "religion"],
        tool_proficiencies=[],
        languages=2,
        equipment=["holy symbol", "prayer book", "5 sticks of incense", "vestments", "common clothes"],
        gold=15,
        feature_name="Shelter of the Faithful",
        feature_description="As an acolyte, you command the respect of those who share your faith. You and your companions can expect free healing and care at temples of your faith.",
        personality_traits=[
            "I idolize a particular hero of my faith and constantly refer to that person's deeds.",
            "I can find common ground between the fiercest enemies, empathizing with them.",
            "I see omens in every event and action.",
            "Nothing can shake my optimistic attitude.",
        ],
        ideals=[
            "Tradition. The ancient traditions of worship must be preserved.",
            "Charity. I always try to help those in need.",
            "Change. We must help bring about the changes the gods are constantly working in the world.",
            "Faith. I trust that my deity will guide my actions.",
        ],
        bonds=[
            "I would die to recover an ancient relic of my faith.",
            "I will someday get revenge on the corrupt temple hierarchy.",
            "I owe my life to the priest who took me in when my parents died.",
            "Everything I do is for the common people.",
        ],
        flaws=[
            "I judge others harshly, and myself even more severely.",
            "I put too much trust in those who wield power within my temple.",
            "My piety sometimes leads me to blindly trust those that profess faith.",
            "I am inflexible in my thinking.",
        ],
    ),
    "criminal": BackgroundData(
        id="criminal",
        display_name="Criminal",
        description="You are an experienced criminal with a history of breaking the law and contacts within the underworld.",
        skill_proficiencies=["deception", "stealth"],
        tool_proficiencies=["thieves' tools", "gaming set"],
        languages=0,
        equipment=["crowbar", "dark common clothes with hood"],
        gold=15,
        feature_name="Criminal Contact",
        feature_description="You have a reliable and trustworthy contact who acts as your liaison to a network of other criminals.",
        personality_traits=[
            "I always have a plan for when things go wrong.",
            "I am always calm, no matter the situation.",
            "The first thing I do in a new place is note exits and hiding spots.",
            "I would rather make a new friend than a new enemy.",
        ],
        ideals=[
            "Honor. I don't steal from others in the trade.",
            "Freedom. Chains are meant to be broken, as are those who would forge them.",
            "Charity. I steal from the wealthy so that I can help people in need.",
            "Greed. I will do whatever it takes to become wealthy.",
        ],
        bonds=[
            "I'm trying to pay off an old debt I owe to a generous benefactor.",
            "Someone I loved died because of a mistake I made.",
            "I'm guilty of a terrible crime and I hope to redeem myself.",
            "My ill-gotten gains go to support my family.",
        ],
        flaws=[
            "When I see something valuable, I can't think about anything but how to steal it.",
            "When faced with a choice between money and my friends, I usually choose the money.",
            "An innocent person is in prison for a crime that I committed.",
            "I have a weakness for the vices of the city.",
        ],
    ),
    "folk_hero": BackgroundData(
        id="folk_hero",
        display_name="Folk Hero",
        description="You come from a humble social rank, but you are destined for so much more. Already people whisper your name.",
        skill_proficiencies=["animal_handling", "survival"],
        tool_proficiencies=["artisan's tools", "vehicles (land)"],
        languages=0,
        equipment=["artisan's tools", "shovel", "iron pot", "common clothes"],
        gold=10,
        feature_name="Rustic Hospitality",
        feature_description="Since you come from the common folk, you fit in among them with ease. You can find a place to hide, rest, or recuperate among commoners.",
        personality_traits=[
            "I judge people by their actions, not their words.",
            "If someone is in trouble, I'm always ready to lend help.",
            "When I set my mind to something, I follow through.",
            "I have a strong sense of fair play.",
        ],
        ideals=[
            "Respect. People deserve to be treated with dignity.",
            "Fairness. No one should get preferential treatment before the law.",
            "Freedom. Tyrants must not be allowed to oppress the people.",
            "Destiny. Nothing and no one can steer me away from my higher calling.",
        ],
        bonds=[
            "I have a family, but I have no idea where they are.",
            "I worked the land, I love the land, and I will protect the land.",
            "A proud noble once gave me a horrible beating, and I will take my revenge.",
            "My tools are symbols of my past life, and I carry them to remember.",
        ],
        flaws=[
            "The tyrant who rules my land will stop at nothing to see me killed.",
            "I'm convinced of the significance of my destiny.",
            "I have trouble trusting in my allies.",
            "I have a weakness for the pleasures of the simple life.",
        ],
    ),
    "noble": BackgroundData(
        id="noble",
        display_name="Noble",
        description="You understand wealth, power, and privilege. You carry a noble title, and your family owns land.",
        skill_proficiencies=["history", "persuasion"],
        tool_proficiencies=["gaming set"],
        languages=1,
        equipment=["fine clothes", "signet ring", "scroll of pedigree"],
        gold=25,
        feature_name="Position of Privilege",
        feature_description="Thanks to your noble birth, people are inclined to think the best of you. You are welcome in high society.",
        personality_traits=[
            "My eloquent flattery makes everyone I talk to feel important.",
            "The common folk love me for my kindness and generosity.",
            "No one could doubt by looking at my regal bearing that I am above the common folk.",
            "I take great pains to always look my best.",
        ],
        ideals=[
            "Respect. Respect is due to me because of my position.",
            "Responsibility. It is my duty to protect those beneath me.",
            "Independence. I must prove that I can handle myself without my family.",
            "Power. If I can attain more power, no one will tell me what to do.",
        ],
        bonds=[
            "I will face any challenge to win the approval of my family.",
            "My house's alliance with another noble family must be sustained.",
            "Nothing is more important than the other members of my family.",
            "I am in love with the heir of a family that my family despises.",
        ],
        flaws=[
            "I secretly believe that everyone is beneath me.",
            "I hide a truly scandalous secret that could ruin my family.",
            "I too often hear veiled insults and threats in every word.",
            "I have an insatiable desire for carnal pleasures.",
        ],
    ),
    "sage": BackgroundData(
        id="sage",
        display_name="Sage",
        description="You spent years learning the lore of the multiverse. You scoured manuscripts and listened to great thinkers.",
        skill_proficiencies=["arcana", "history"],
        tool_proficiencies=[],
        languages=2,
        equipment=["bottle of black ink", "quill", "small knife", "letter from dead colleague", "common clothes"],
        gold=10,
        feature_name="Researcher",
        feature_description="When you attempt to learn or recall a piece of lore, if you don't know it, you often know where to find it.",
        personality_traits=[
            "I use polysyllabic words that convey the impression of great erudition.",
            "I've read every book in the world's greatest libraries.",
            "I'm used to helping out those who aren't as smart as I am.",
            "There's nothing I like more than a good mystery.",
        ],
        ideals=[
            "Knowledge. The path to power and self-improvement is through knowledge.",
            "Beauty. What is beautiful points us beyond itself toward what is true.",
            "Logic. Emotions must not cloud our logical thinking.",
            "Self-Improvement. The goal of a life of study is the betterment of oneself.",
        ],
        bonds=[
            "It is my duty to protect my students.",
            "I have an ancient text that holds terrible secrets.",
            "I work to preserve a library, university, or scriptorium.",
            "My life's work is a series of tomes on a specific field of lore.",
        ],
        flaws=[
            "I am easily distracted by the promise of information.",
            "Most people scream and run when they see a demon. I stop and take notes.",
            "Unlocking an ancient mystery is worth the price of a civilization.",
            "I speak without really thinking through my words, invariably insulting others.",
        ],
    ),
    "soldier": BackgroundData(
        id="soldier",
        display_name="Soldier",
        description="War has been your life for as long as you care to remember. You trained as a youth and went to war.",
        skill_proficiencies=["athletics", "intimidation"],
        tool_proficiencies=["gaming set", "vehicles (land)"],
        languages=0,
        equipment=["insignia of rank", "trophy from fallen enemy", "bone dice", "common clothes"],
        gold=10,
        feature_name="Military Rank",
        feature_description="You have a military rank from your career as a soldier. Soldiers loyal to your former military organization recognize your authority.",
        personality_traits=[
            "I'm always polite and respectful.",
            "I've lost too many friends, and I'm slow to make new ones.",
            "I face problems head-on. A simple, direct solution is the best path.",
            "I can stare down a hell hound without flinching.",
        ],
        ideals=[
            "Greater Good. Our lot is to lay down our lives in defense of others.",
            "Responsibility. I do what I must and obey just authority.",
            "Independence. When people follow orders blindly, they embrace tyranny.",
            "Might. In life as in war, the stronger force wins.",
        ],
        bonds=[
            "I would still lay down my life for the people I served with.",
            "Someone saved my life on the battlefield.",
            "My honor is my life.",
            "I'll never forget the crushing defeat my company suffered.",
        ],
        flaws=[
            "The monstrous enemy we faced in battle still leaves me quivering with fear.",
            "I have little respect for anyone who is not a proven warrior.",
            "I made a terrible mistake in battle that cost many lives.",
            "My hatred of my enemies is blind and unreasoning.",
        ],
    ),
}


def get_background(background_id: str) -> BackgroundData | None:
    """Get a background by ID."""
    return BACKGROUNDS.get(background_id.lower())


def get_all_backgrounds() -> List[BackgroundData]:
    """Get all backgrounds."""
    return list(BACKGROUNDS.values())


def get_background_skill_options(background_id: str) -> List[str]:
    """Get the skill proficiencies granted by a background."""
    background = get_background(background_id)
    return background.skill_proficiencies if background else []
