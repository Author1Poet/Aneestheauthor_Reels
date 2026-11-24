import json, re
def hook(*lines):
    out=[]; on=False
    for ln in lines:
        row=[]
        for w in ln.split():
            st=w.startswith('*'); en=w.endswith('*') and len(w.strip('*'))>0
            if st: on=True
            row.append([w.strip('*'), on])
            if en or (st and w.endswith('*')): on=False
        out.append(row)
    return out
def M(who, text, emo=None, **kw):
    d=dict(k="msg", who=who, text=text); 
    if emo: d["emo"]=emo
    d.update(kw); return d
def G(who, ghost, emo=None, **kw):
    d=dict(k="msg", who=who, ghost=ghost)
    if emo: d["emo"]=emo
    d.update(kw); return d
def B(dur, emo=None, look=None, pose=None, focus=None, **kw):
    d=dict(k="beat", dur=dur)
    if emo: d["emo"]=emo
    if look: d["look"]=look
    if pose: d["pose"]=pose
    if focus is not None: d["focus"]=focus
    d.update(kw); return d
def card(t,title,text,when,red=False):
    d=dict(t=t,title=title,text=text,when=when)
    if red: d["red"]=True
    return d
def write(n, spec):
    spec.setdefault("id", n); spec.setdefault("hook_y",1480); spec.setdefault("hook_size",64); spec.setdefault("follow","New story every night at 10 PM")
    spec.setdefault("seed", n)
    json.dump(spec, open(f"ep{n}.json","w"), indent=1, ensure_ascii=False)

# ---------------------------------------------------------------- EP3
write(3, dict(chars=["hamza","abbu"], scenes=[dict(kind="desk",variant="hostel"), dict(kind="livingroom")], layout=["R","L"],
 places=["Hostel  ·  10:04 PM","Home  ·  10:04 PM"], time_label="Today 10:04 PM", start_emo=["tired","soft"], start_look=["phone","phone"],
 lock=dict(dur=2.7,date="Wednesday, 25 November",time="10:04",cards=[
   card(.15,"Abbu","Beta paise bhej diye hain. Mil gaye? - Abbu","9:41 PM"),
   card(.55,"Easypaisa","Rs 25,000 received from ABBU","9:41 PM"),
   card(.95,"Abbu","Khana kha liya? - Abbu","9:58 PM"),
   card(1.35,"Abbu","Kal bhi phone karunga - Abbu","10:02 PM")]),
 hook=hook("Abbu *sent* Rs 25,000.","But *where* did it come from?"),
 beats=[B(1.0,["tired","soft"],["phone","phone"],focus=0),
  M(1,"Beta paise mil gaye? - Abbu",["soft","soft"]),
  M(0,"mil gaye abbu. shukriya",["soft","soft"]),
  M(0,"ek baat puchun? aap har message ke end me apna naam kyun likhte hain 😭",["smile","soft"]),
  M(1,"Pata nahi kaun parh raha ho. - Abbu",["smile","laugh"],pause=.5),
  M(0,"abbu 😭 mere alawa kaun parhega",["laugh","smile"]),
  B(1.0,["soft","soft"],["cam","phone"],focus=1),
  M(0,"abbu itne paise kahan se aaye? fees to 40 hazaar thi",["worry","nervous"]),
  M(1,"Bachat thi beta. - Abbu",["nervous","worry"],hes=[.5,.8,"away"]),
  M(0,"kal fahad ne ek OLX ad bheji thi. Honda 70. 2014 model. Gulberg",["nervous","worry"],pause=.5),
  M(1,"Purani thi beta. Engine ka kaam nikalta rehta tha. - Abbu",["hurt","hurt"],hes=[.4,1.2,"away"],focus=1),
  M(0,"abbu wo aapki bike thi",["cry","hurt"],pose=["face",None],pause=.9,focus=0),
  M(1,"Masjid paas hai. Paidal chala jaata hoon. Sehat ke liye acha hai. - Abbu",["soft","cry"],pose=["chest",None],pause=1.0),
  G(0,"abbu main sharminda hoon",["cry","soft"],ghost_hold=1.1,pause=.4),
  M(0,"main wapas la dunga abbu. aapki bike bhi",["cry","soft"],focus=1),
  M(1,"Pehle degree. - Abbu",["soft","cry"],pause=.8),
  M(1,"Baap ki bike beta hi chalata hai. Tum chalaoge. - Abbu",["soft","cry"],burst=True,stay=2.2,focus=0,pause=1.2)],
 closer=["Some fathers walk","so you can ride."], cta="Send this to your Abbu", pad=[98.0,146.83,196.0,246.94]))

# ---------------------------------------------------------------- EP4
write(4, dict(chars=["daniyal","zoya"], scenes=[dict(kind="desk",variant="hostel"), dict(kind="car",variant="street")], layout=["R","L"],
 places=["Office  ·  11:41 PM","Outside his building  ·  11:41 PM"], time_label="Today 11:41 PM", start_emo=["tired","nervous"], start_look=["phone","phone"],
 lock=dict(dur=2.7,date="Thursday, 26 November",time="11:41",cards=[
   card(.15,"Zoya","ok","6:12 PM"),
   card(.55,"Zoya","busy. talk later","8:40 PM"),
   card(.95,"Zoya","👍","10:15 PM"),
   card(1.35,"Birthday","Your birthday ends in 19 minutes","11:41 PM",True)]),
 hook=hook("It was his *birthday.*","Zoya only sent *👍*"),
 beats=[B(1.0,["tired","nervous"],["phone","phone"],focus=0),
  M(0,"zoya it's 11:41",["tired","nervous"]),
  M(1,"yes? lol",["smirk","annoyed"]),
  M(0,"my birthday ends in 19 minutes",["hurt","smirk"]),
  M(1,"oh is it today? 🙈",["smirk","hurt"],pause=.6),
  M(0,"wow. ok.",["hurt","nervous"],pause=.7),
  M(1,"don't be dramatic. what are you doing",["nervous","hurt"]),
  M(0,"working. like every other day. you're right, it's just a day",["sad","worry"],pose=["face",None],focus=0,pause=.8),
  M(1,"daniyal. look outside your window",["soft","shock"],focus=1),
  M(0,"it's the 9th floor zoya",["annoyed","soft"]),
  M(1,"just look",["smile","nervous"]),
  B(1.3,["shock","smile"],["away","cam"],focus=0),
  M(0,"ZOYA",["shock","smirk"],burst=True),
  M(0,"is that my mother. holding a cake. in a parking lot",["laugh","laugh"],pose=["mouth",None]),
  M(1,"your ammi brought biryani too. come down before it gets cold",["laugh","laugh"],focus=1),
  M(0,"i thought you forgot",["cry","soft"],pose=["face",None],pause=.9,focus=0),
  M(1,"i hid it for 3 weeks. you are a terrible detective",["soft","relief"],pause=.5),
  M(0,"coming. nobody sing without me",["laugh","laugh"],stay=2.2,pause=1.0)],
 closer=["Sometimes the quiet ones","are planning your whole day."], cta="Tag the person who never forgets you", pad=[110.0,164.81,220.0,277.18]))

# ---------------------------------------------------------------- EP5
write(5, dict(chars=["hamza","ammi"], scenes=[dict(kind="desk",variant="hostel"), dict(kind="kitchen",variant="dawn")], layout=["R","L"],
 places=["Hostel  ·  5:21 AM","Home  ·  5:21 AM"], time_label="Today 5:21 AM", start_emo=["worry","soft"], start_look=["phone","phone"],
 lock=dict(dur=2.7,date="Friday, 27 November",time="5:21",cards=[
   card(.15,"Ammi","Beta uth gaye? Naashta mein kya banaun?","5:02 AM"),
   card(.55,"Ammi","Aaloo paratha?","5:06 AM"),
   card(.95,"Daewoo Express","Ticket confirmed: Lahore → Multan, 6:30 AM","4:48 AM"),
   card(1.35,"Notes","How do I tell Ammi...","3:12 AM",True)]),
 hook=hook("He rehearsed one sentence","all night. She'd *already* known."),
 beats=[B(1.0,["worry","soft"],["phone","phone"],focus=0),
  M(1,"Beta uth gaye? Naashta mein kya banaun?",["soft","nervous"]),
  G(0,"ammi meri job chali gayi",["worry","soft"],ghost_hold=1.2,pause=.4),
  M(0,"kuch bhi ammi",["tired","soft"]),
  M(1,"Aaloo paratha banaun? Ya anda?",["soft","nervous"]),
  M(0,"ammi main aaj ghar aa raha hoon",["nervous","soft"],pause=.5),
  M(1,"Acha! Kitne din ke liye?",["soft","worry"]),
  M(0,"pata nahi. shayad kuch din. shayad zyada",["sad","worry"],hes=[.5,.9,"away"],focus=0,pause=.9),
  M(0,"ammi mujhe job se nikal diya gaya",["cry","soft"],pose=["face",None],pause=1.1),
  M(1,"Pata hai",["soft","shock"],focus=1,pause=.8),
  M(0,"kya? kaise?",["shock","soft"]),
  M(1,"Fahad ki ammi ne do din pehle bata diya tha",["soft","shock"]),
  M(0,"to aap ne kuch kaha kyun nahi",["hurt","soft"],pause=.5),
  M(1,"Tum khud batate to acha lagta. Isliye intezar kiya",["soft","cry"],pose=["chest",None],focus=1,pause=.9),
  M(1,"Tumhare kamre ki chadar badal di hai. Bas jaldi aa jao",["soft","cry"],burst=True,pause=.8),
  M(1,"Naukri gayi hai beta. Tum to nahi gaye",["soft","cry"],pose=["chest","face"],focus=0,stay=2.4,pause=1.3)],
 closer=["Home is the only place","that never asks","what you lost."], cta="Send this to someone who needs to hear it", pad=[123.47,185.0,246.94,293.66]))

# ---------------------------------------------------------------- EP6
write(6, dict(chars=["sara","zoya"], scenes=[dict(kind="bedroom"), dict(kind="desk",variant="packing")], layout=["L","R"],
 places=["Home  ·  11:40 PM","Packing  ·  11:40 PM"], time_label="Today 11:40 PM", start_emo=["tired","soft"], start_look=["phone","phone"],
 lock=dict(dur=2.7,date="Saturday, 28 November",time="11:40",cards=[
   card(.15,"Zoya","🎙 Voice message (4:12)","Tuesday"),
   card(.55,"Zoya","🎙 Voice message (0:48)","Wednesday"),
   card(.95,"Zoya","sara? you there?","Thursday"),
   card(1.35,"Unplayed","3 voice messages from Zoya","Now",True)]),
 hook=hook("She never opened","Zoya's *4:12 voice note.*"),
 beats=[B(1.0,["tired","soft"],["phone","phone"],focus=0),
  M(1,"heyyy awake?",["soft","soft"]),
  M(0,"yes!! sorry i've been so busy. i'll listen to your voice notes this weekend i promise",["smile","soft"]),
  M(1,"it's okay 🙂 no rush",["soft","hurt"],pause=.6),
  M(0,"how's work? still crazy?",["soft","hurt"]),
  M(1,"ya. btw my flight is at 6am lol",["nervous","shock"],hes=[.5,.7,"away"]),
  M(0,"6am where? for the conference??",["worry","nervous"]),
  M(1,"dubai. the job thing. i told you in the voice note. like 3 days ago",["hurt","shock"],pause=.8,focus=1),
  M(0,"WHAT",["shock","hurt"],burst=True),
  M(0,"zoya you're LEAVING?",["shock","cry"],pose=["mouth",None],focus=0,pause=.7),
  M(1,"for 2 years. i didn't know how to say it in a text",["cry","hurt"],pose=[None,"face"],pause=1.0),
  B(1.2,["sad","cry"],["phone","away"],focus=0),
  M(0,"i'm playing it right now",["cry","hurt"],pose=["face",None]),
  M(0,"you said 'thank you for never being too busy for me'",["cry","cry"],pause=1.0),
  M(0,"i was ALWAYS too busy",["cry","cry"],pause=.8),
  M(1,"you were there when it mattered. that's all i meant",["soft","cry"],focus=1,pause=.8),
  M(0,"i'm coming to the airport. 6am",["cry","soft"]),
  M(1,"sara that's 4am drive. nobody does that",["soft","cry"]),
  M(0,"i do",["cry","cry"],stay=2.4,focus=0,pause=1.2)],
 closer=["Play the voice note.","Some goodbyes arrive","in 4 minutes and 12 seconds."], cta="Send this to someone whose voice notes you've been ignoring", pad=[98.0,146.83,196.0,246.94]))

# ---------------------------------------------------------------- EP7
write(7, dict(chars=["sara","rayyan"], scenes=[dict(kind="bedroom"), dict(kind="cafe",variant="closing")], layout=["L","R"],
 places=["Home  ·  11:59 PM","Closing the café  ·  11:59 PM"], time_label="Today 11:59 PM", start_emo=["sad","tired"], start_look=["phone","far"],
 lock=dict(dur=2.7,date="Sunday, 29 November",time="11:59",cards=[
   card(.15,"Unknown number","Happy birthday Abbu 🤍","11:59 PM"),
   card(.55,"Unknown number","I know this isn't your number anymore","11:59 PM"),
   card(.95,"Unknown number","I just didn't know where else to send it","12:00 AM"),
   card(1.35,"Wrong number?","Tap to reply","Now",True)]),
 hook=hook("She texts her late father","*every birthday.*","Tonight, *he replied.*"),
 beats=[B(1.0,["sad","tired"],["phone","far"],focus=0),
  M(0,"Happy birthday Abbu 🤍",["cry","soft"],pause=.8),
  M(0,"I know this isn't your number anymore. I just didn't know where else to send it",["cry","worry"],pause=.8),
  B(1.2,["cry","shock"],["phone","phone"],pose=[None,"chest"],focus=1),
  M(1,"hi. i think this is a wrong number",["nervous","shock"],hes=[.4,.9,"away"]),
  M(0,"oh god. i'm so sorry",["shock","soft"],pose=["mouth",None]),
  M(1,"please don't apologize. i'm so sorry about your father",["soft","cry"],focus=1),
  M(0,"it's been 2 years. i text him every birthday. it's the one number i couldn't delete",["cry","soft"],pause=1.0,focus=0),
  M(1,"weird thing to say but you're the first person who texted me today",["soft","shock"],pause=.6),
  M(1,"it's my birthday too",["soft","shock"],burst=True,pause=.8),
  M(0,"no way",["shock","soft"]),
  M(1,"so technically i'm receiving your dad's wish. happy birthday to him. and thank you",["soft","cry"],pose=[None,"chest"],focus=1,pause=.9),
  M(0,"thank you for not blocking me",["laugh","cry"]),
  M(1,"you can text this number every birthday. i won't change it",["soft","cry"],pause=.9),
  M(0,"you'd do that?",["cry","soft"]),
  M(1,"someone should be there to read it",["soft","cry"],focus=0,stay=2.6,pause=1.3)],
 closer=["Some wrong numbers","arrive right on time."], cta="Send this to someone who is missing someone", pad=[110.0,164.81,196.0,261.63]))

# ---------------------------------------------------------------- EP8
write(8, dict(chars=["abbu","ammi"], scenes=[dict(kind="car",variant="pump"), dict(kind="kitchen",variant="night")], layout=["R","L"],
 places=["Petrol pump  ·  10:52 PM","Home  ·  10:52 PM"], time_label="Today 10:52 PM", start_emo=["soft","soft"], start_look=["phone","phone"],
 lock=dict(dur=2.7,date="Monday, 30 November",time="10:52",cards=[
   card(.15,"Zareena","Kuch nahi","1993",False),
   card(.55,"Zareena","Kuch nahi chahiye","2004"),
   card(.95,"Zareena","Aap thak gaye honge, kuch nahi","2019"),
   card(1.35,"Zareena","Mogre ke phool","Tonight",True)]),
 hook=hook("Thirty years of *'kuch nahi.'*","Tonight she asked for *something.*"),
 beats=[B(1.0,["soft","soft"],["phone","phone"],focus=0),
  M(0,"Kuch laana hai? - Abbu",["soft","soft"]),
  M(1,"Nahi. Aap aa jao bas",["soft","soft"]),
  M(0,"Pakka? Dukaan band hone wali hai - Abbu",["soft","soft"]),
  M(1,"Kuch nahi chahiye. Aap jaldi aa jao",["soft","soft"],pause=.5),
  M(0,"Theek hai - Abbu",["soft","nervous"],pause=.9),
  B(1.2,["soft","nervous"],["phone","away"],focus=1),
  G(1,"mogre ke phool",["soft","soft"],ghost_hold=1.3,pause=.4),
  M(1,"Raat bohat ho gayi. Pehle gaari mein petrol dalwa lena",["soft","worry"]),
  M(0,"Petrol dal gaya. Ab bol - Abbu",["smirk","shock"],pause=.6),
  M(1,"Kuch nahi",["nervous","worry"],pause=.7),
  M(0,"Zareena. Tees saal ho gaye. Jab tum kuch nahi kehti ho to mujhe pata hota hai kuch hai - Abbu",["soft","cry"],focus=0,pause=1.0),
  M(1,"mogre ke phool. aaj achanak yaad aa gaye. shaadi wale din ke. par ab raat ko kahan milenge",["cry","soft"],pose=["chest",None],focus=1,pause=1.0),
  M(0,"Aa raha hoon - Abbu",["soft","soft"]),
  M(1,"Suno. pagal ho. raat ke 11 baj gaye hain",["laugh","smile"]),
  M(0,"Gate pe aa jao - Abbu",["smile","shock"],pause=.8),
  M(1,"kya?",["shock","smile"],pause=.5),
  M(0,"Teen dukanon pe dhoonda. Aakhri wale ne kaha baji kal aaiye. Maine kaha meri biwi ne tees saal mein pehli baar kuch manga hai - Abbu",["soft","cry"],stay=2.6,focus=1,pause=1.3)],
 closer=["Love is hearing","what 'nothing' means."], cta="Send this to your parents", pad=[110.0,164.81,207.65,277.18]))

# ---------------------------------------------------------------- EP9
write(9, dict(chars=["noor","daniyal"], scenes=[dict(kind="cafe",variant="closing"), dict(kind="car",variant="street")], layout=["L","R"],
 places=["Café  ·  9:14 PM","Outside the café  ·  9:14 PM"], time_label="Today 9:14 PM", start_emo=["hurt","nervous"], start_look=["phone","phone"],
 lock=dict(dur=2.7,date="Tuesday, 1 December",time="9:14",cards=[
   card(.15,"Daniyal","hey","9:12 PM"),
   card(.55,"Daniyal","Missed call","9:12 PM"),
   card(.95,"Last message from Daniyal","22 days ago","Nov 9"),
   card(1.35,"Daniyal","are you there?","9:13 PM",True)]),
 hook=hook("He ignored her *22 days.*","Tonight he texted *'hey'*"),
 beats=[B(1.0,["hurt","nervous"],["phone","phone"],focus=0),
  M(1,"hey",["nervous","shock"],pause=.9),
  B(1.0,["shock","nervous"],["phone","phone"],focus=0),
  M(1,"i know it's been a while",["nervous","hurt"]),
  M(0,"22 days",["hurt","nervous"],pause=.6),
  M(1,"you counted?",["nervous","hurt"]),
  M(0,"every one of them. i'm done counting now",["sad","worry"],focus=0,pause=.9),
  M(1,"i was going through a lot. i didn't know how to talk to anyone",["sad","soft"]),
  M(0,"i know. i wanted to be that person. you never let me",["hurt","hurt"],pause=.9),
  M(1,"can we talk? i'm outside",["nervous","shock"],focus=1),
  M(0,"outside where",["shock","nervous"]),
  M(1,"the café. in my car",["nervous","shock"],pause=.6),
  M(0,"the one with the broken tail light",["soft","shock"],pause=.9),
  M(1,"you saw me?",["shock","soft"]),
  M(0,"since 8:40. i didn't come out. i wanted to see if you'd come in",["soft","cry"],pose=["chest",None],focus=0,pause=1.0),
  M(1,"i'm sorry noor. i'm coming in",["cry","hurt"],focus=1,pause=.7),
  G(0,"please come in",["cry","soft"],ghost_hold=1.2,pause=.4),
  M(0,"don't. i'm not angry anymore. that's why you can't come in",["soft","cry"],pause=1.0),
  M(0,"i missed you for 22 days. i won't wait 22 more",["soft","cry"],burst=True,pause=.9),
  M(0,"drive safe daniyal. text me when you reach",["soft","cry"],focus=0,stay=2.6,pause=1.3)],
 closer=["Missing you","isn't the same as","choosing you."], cta="Send this to someone who needs to hear it", pad=[123.47,185.0,246.94,293.66]))
