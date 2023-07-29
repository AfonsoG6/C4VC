from unicodedata import normalize
from dotenv import load_dotenv
from asyncio import Lock
from discord import *
import re
import os

#-----------------------Initiate all global variables--------------------------

END_SESSION_MSG = "`+------------------------------------+`" + "\n" \
                + "`|           END OF SESSION           |`" + "\n" \
                + "`+------------------------------------+`"

# Invisible characters are used for uniqueness
C4VC_TC_PRE = "🔒"
C4VC_TTC_SUF = "᲼🇹"
C4VC_PTC_SUF = "᲼🇵"
C4VC_ROLE_SUF = "᲼role"

TTC_MESSAGE = "This text channel is now **Transient**. It will be deleted when everyone leaves the VC."
MAKE_TTC_COMMAND = "+transient"
MAKE_TTC_COMMAND_ABREV = "+t"

PTC_MESSAGE = "This text channel is now **Permanent**. It won't be deleted even if everyone leaves the VC."
MAKE_PTC_COMMAND = "+permanent"
MAKE_PTC_COMMAND_ABREV = "+p"

DO_SEND_ESMSG = True	# If bot sends a message marking the end of the session in a PTC

client = Client(intents=Intents.all())

locks:dict = {}

#---------------------------------Functions------------------------------------

def printlvl(lvl:int, text:str):
    text = normalize("NFKD", text)
    pattern = re.compile(pattern = r"[^\x00-\x7F]+", flags = re.UNICODE)
    onlyAsciiText = pattern.sub(r'', text)
    print("\t"*lvl + onlyAsciiText)

def makeValidName(name:str) -> str :
    name = normalize('NFKD', name)
    # Remove emojis
    pattern = re.compile(pattern = r"[^a-zA-Z0-9_\- ]+", flags = re.UNICODE)
    name = pattern.sub('', name)
    # Replace spaces with an allowed invisible character
    name = name.replace(" ", "᲼")
    # OPTIONAL: Remove underscores at the begining
    # while len(name) >= 2 and name[0] == "_":
    #     name = name[1:]
    # Transform into lowercase
    name = name.lower()
    return name

def getRoleName(vcName:str) -> str :
    return makeValidName(vcName) + C4VC_ROLE_SUF

def getTTCName(vcName:str) -> str :
    return C4VC_TC_PRE + makeValidName(vcName) + C4VC_TTC_SUF

def getPTCName(vcName:str) -> str :
    return C4VC_TC_PRE + makeValidName(vcName) + C4VC_PTC_SUF

def getPTCNameFromTTCName(ttcName:str) -> str :
    return ttcName.replace(C4VC_TTC_SUF, C4VC_PTC_SUF)

def getTTCNameFromPTCName(ptcName:str) -> str :
    return ptcName.replace(C4VC_PTC_SUF, C4VC_TTC_SUF)

def isTTC(tcName:str) -> bool:
    return re.search(pattern = rf"{C4VC_TTC_SUF}$", string=tcName) != None

def isPTC(tcName:str) -> bool:
    return re.search(pattern = rf"{C4VC_PTC_SUF}$", string=tcName) != None

def getTopic(vcName:str, tcName:str) -> str :
    return f"This text channel is private for people on the VC: **{vcName}**\n" \
    + (TTC_MESSAGE if isTTC(tcName) else PTC_MESSAGE).replace("now", "currently") + "\n" \
    + f"You can change this behavior by writing '{MAKE_PTC_COMMAND}'/'{MAKE_PTC_COMMAND_ABREV}' or '{MAKE_TTC_COMMAND}'/'{MAKE_TTC_COMMAND_ABREV}' in this channel."

def getUpdatedTopic(tc:TextChannel, lvl:int) -> str :
    # This function is flimsy, it assumes the topic is in a specific format found in getTopic()
    lines = tc.topic.split("\n")
    if len(lines) != 3:
        printlvl(lvl, f"Invalid topic format: '{tc.topic}'")
        raise Exception("Invalid topic format")
    newTopic = lines[0] + "\n" \
    + (TTC_MESSAGE if isTTC(tc.name) else PTC_MESSAGE).replace("now", "currently") + "\n" \
    + lines[2]
    printlvl(lvl, f"Updated topic: '{newTopic}'")
    return newTopic

def findRole(guild:Guild, vcName:str) -> Role or None :
    roleName = getRoleName(vcName)
    for role in guild.roles:
        if role.name == roleName:
            return role
    return None

async def findTC(guild:Guild, vcName:str) -> TextChannel or None :
    ttcName = getTTCName(vcName)
    ptcName = getPTCName(vcName)
    ttc = None
    ptc = None
    for tc in guild.text_channels:
        if tc.name == ttcName:
            ttc = tc
        elif tc.name == ptcName:
            ptc = tc
    if ttc != None and ptc != None:
        await ttc.delete()
        return ptc
    elif ttc != None:
        return ttc
    elif ptc != None:
        return ptc

async def setupRole(vc:VoiceChannel, lvl:int) -> Role :
    guild = vc.guild
    roleName = getRoleName(vc.name)
    role = findRole(guild, vc.name)
    if role != None:
        printlvl(lvl, f"Role '{roleName}' already exists.")
    else:
        printlvl(lvl, f"Creating role '{roleName}'")
        role = await guild.create_role(name=roleName)
        if role == None:
            raise Exception("Couldn't create role")
    await resetRoleMembers(vc, role, lvl=lvl+1)
    return role

async def setupTC(vc:VoiceChannel, role:Role, lvl:int) -> TextChannel :
    guild = vc.guild
    tc: TextChannel = await findTC(guild, vc.name)
    if tc != None:
        printlvl(lvl, f"Text channel '{tc.name}' already exists")
        # Remove all permissions from the channel
        await tc.edit(sync_permissions=False)
        for perm in tc.overwrites:
            printlvl(lvl, f"Removing permission '{perm}' from '{tc.name}'")
            await tc.set_permissions(perm, overwrite=None)
        await tc.set_permissions(guild.default_role, send_messages=False, read_messages=False)
        await tc.set_permissions(role, send_messages=True, read_messages=True)
    else:
        ttcName = getTTCName(vc.name)
        printlvl(lvl, f"Creating text channel '{ttcName}'")
        tc = await guild.create_text_channel(name=ttcName, category=vc.category)
        if tc == None:
            raise Exception("Couldn't create TC")
        # Remove all permissions from the channel
        await tc.edit(sync_permissions=False, topic=getTopic(vc.name, tc.name))
        for perm in tc.overwrites:
            await tc.set_permissions(perm, overwrite=None)
        await tc.set_permissions(guild.default_role, send_messages=False, read_messages=False)
        await tc.set_permissions(role, send_messages=True, read_messages=True)
    return tc

async def setupRoleAndTC(vc:VoiceChannel, lvl:int):
    vcValidName = makeValidName(vc.name)
    if vcValidName in locks.keys():
        lock = locks[vcValidName]
    else:
        lock = locks[vcValidName] = Lock()

    async with lock:
        role = await setupRole(vc, lvl=lvl)
        await setupTC(vc, role, lvl=lvl)

async def resetRoleMembers(vc:VoiceChannel, role:Role, lvl:int):
    printlvl(lvl, f"Resetting members of role '{role.name}'")
    for member in role.members:
        printlvl(lvl+1, f"Removing role '{role.name}' from '{member.name}'")
        await member.remove_roles(role, reason="Resetting Role")
    for member in vc.members:
        printlvl(lvl+1, f"Adding role '{role.name}' to '{member.name}'")
        await member.add_roles(role, reason="Resetting Role and User is in VC")

async def processUserLeave(vc:VoiceChannel, member:Member, lvl:int):
    guild = vc.guild

    printlvl(lvl, f"User '{member.name}' left VC '{vc.name}'")
    role = findRole(guild, vc.name)
    if role != None:
        await member.remove_roles(role, reason="User left VC")

    if len(vc.members) <= 0:
        tc = await findTC(guild, vc.name)

        if role != None and len(role.members) > 0:
            await resetRoleMembers(vc, role, lvl=lvl+1)
        
        if tc != None and isTTC(tc.name):
            printlvl(lvl+1, f"Deleting TTC '{tc.name}' from '{guild.name}'")
            await tc.delete()

        if tc != None and isPTC(tc.name):
            if role == None:
                await setupRoleAndTC(vc, lvl=lvl+1)
                role = findRole(guild, vc.name)
            if DO_SEND_ESMSG:
                printlvl(lvl+1, f"Sending END_SESSION_MSG to PTC '{tc.name}' from '{guild.name}'")
                await tc.send(END_SESSION_MSG)
        
        await cleanUp(guild, lvl+1)

async def processUserJoin(vc:VoiceChannel, member:Member, lvl:int):
    printlvl(lvl, f"User '{member.name}' joined VC '{vc.name}'")
    role = findRole(vc.guild, vc.name)
    tc = await findTC(vc.guild, vc.name)
    if role == None or tc == None:
        await setupRoleAndTC(vc, lvl=lvl+1)
        role = findRole(vc.guild, vc.name)
    await member.add_roles(role, reason="User joined VC")

async def makePermanentTC(tc:TextChannel, lvl:int):
    if isTTC(tc.name):
        printlvl(lvl, f"Making '{tc.name}' from '{tc.guild.name}' Permanent")
        await tc.edit(name=getPTCNameFromTTCName(tc.name))
        await tc.edit(topic=getUpdatedTopic(tc, lvl+1))
        await tc.send(PTC_MESSAGE)
    elif isPTC(tc.name):
        printlvl(lvl, f"Tried to make '{tc.name}' from '{tc.guild.name}' Permanent. But it is already Permanent")
        await tc.send("This text channel is already permanent.")
    else:
        await tc.send("This text channel is not managed by C4VC.")

async def makeTransientTC(tc:TextChannel, lvl:int):
    if isPTC(tc.name):
        printlvl(lvl, f"Making '{tc.name}' from '{tc.guild.name}' Transient")
        await tc.edit(name=getTTCNameFromPTCName(tc.name))
        await tc.edit(topic=getUpdatedTopic(tc, lvl+1))
        await tc.send(TTC_MESSAGE)
    elif isTTC(tc.name):
        printlvl(lvl, f"Tried to make '{tc.name}' from '{tc.guild.name}' Transient. But it is already Transient")
        await tc.send("This text channel is already transient.")
    else:
        await tc.send("This text channel is not managed by C4VC.")

async def cleanUp(guild:Guild, lvl:int):
    expectedTCNames = []
    expectedRoleNames = []

    printlvl(lvl, f"Cleaning up '{guild.name}'")
    for vc in guild.voice_channels:
        expectedTCNames += [getTTCName(vc.name), getPTCName(vc.name)]
        expectedRoleNames += [getRoleName(vc.name)]

    for tc in guild.text_channels:
        if re.search(pattern = rf"({C4VC_TTC_SUF}|{C4VC_PTC_SUF})$", string=tc.name) != None \
                and tc.name not in expectedTCNames:
            printlvl(lvl+1, f"Deleting TC '{tc.name}'")
            await tc.delete()

    for role in guild.roles:
        if re.search(pattern = rf"{C4VC_ROLE_SUF}$", string=role.name) != None \
                and role.name not in expectedRoleNames:
            printlvl(lvl+1, f"Deleting Role '{role.name}'")
            await role.delete()

async def renameTC(guild:Guild, beforeName:str, afterName:str) -> bool:
    tc = await findTC(guild, beforeName)

    if tc == None:
        printlvl(1, f"There is currently no TC for this VC.")
        return False

    if isTTC(tc.name):
        newTCName = getTTCName(afterName)
    elif isPTC(tc.name):
        newTCName = getPTCName(afterName)

    printlvl(1, f"Renaming TC {tc.name} to {newTCName}")
    await tc.edit(name=newTCName)
    return True


async def renameRole(guild:Guild, beforeName:str, afterName:str) -> bool:
    role = findRole(guild, beforeName)

    if role == None:
        printlvl(1, f"There is currently no Role for this VC.")
        return False

    newRoleName = getRoleName(afterName)

    printlvl(1, f"Renaming Role {role.name} to {newRoleName}")
    await role.edit(name=newRoleName)
    return True

#----------------------------------Events--------------------------------------

@client.event
async def on_ready():
    #await client.change_presence(activity=Game(""))

    for guild in client.guilds:
        printlvl(0, f"Setting up guild '{guild.name}'")
        for vc in guild.voice_channels:
            if len(vc.members) > 0:
                printlvl(1, f"Setting up VC '{vc.name}'")
                await setupRoleAndTC(vc, lvl=2)
    printlvl(0, f"Finished setup. Logged in as {client.user}")

@client.event
async def on_voice_state_update(member:Member, before:VoiceState, after:VoiceState):
    if (before.channel != None) and ((after.channel == None) or (after.channel.id != before.channel.id)):
        await processUserLeave(before.channel, member, lvl=0)
    if (after.channel != None) and ((before.channel == None) or (before.channel.id != after.channel.id)):
        await processUserJoin(after.channel, member, lvl=0)

@client.event
async def on_message(message:Message):
    tc = message.channel
    if message.author.bot:
        return
    if message.content in [MAKE_TTC_COMMAND, MAKE_TTC_COMMAND_ABREV]:
        await makeTransientTC(tc, 0)
    elif message.content in [MAKE_PTC_COMMAND, MAKE_PTC_COMMAND_ABREV]:
        await makePermanentTC(tc, 0)

@client.event
async def on_guild_channel_update(before:abc.GuildChannel, after:abc.GuildChannel):
    if not (isinstance(before, VoiceChannel) and isinstance(after, VoiceChannel)):
        return
    if before.name == after.name:
        return

    guild = before.guild
    printlvl(0, f"VC {before.name} from {guild} was renamed to {after.name}")
    didChangeRole = await renameRole(guild, before.name, after.name)
    didChangeTC = await renameTC(guild, before.name, after.name)
    if (not didChangeRole or not didChangeTC) and len(after.members) > 0:
        await setupRoleAndTC(after, 2)

#-----------------------------Run and Connect Bot------------------------------

try:
    load_dotenv()
    token = os.getenv('TOKEN')
    if token == None:
        print("[ERROR] Please provide a token in the .env file")
        input("        Press ENTER to exit...")
        exit(1)
    client.run(token)
except Exception as e:
    print(e)