#"Application ID" 		857670450175934524
#"Token"				ODU3NjcwNDUwMTc1OTM0NTI0.YNS92g.muxqEFYWSsBHMQ7JUFpbfGNJ3qs
#"Permissions Integer"	8

#R2K guild.id 			131480252500279296

#URL for invite			https://discordapp.com/oauth2/authorize?client_id=857670450175934524&scope=bot&permissions=8

#Compile to exe			pyinstaller chat4voicecall.py -F

from asyncio import Lock
from discord import *
import re

#-----------------------Initiate all global variables--------------------------

END_SESSION_MSG = \
	  "`+------------------------------------+`" + "\n" \
	+ "`|           END OF SESSION           |`" + "\n" \
	+ "`+------------------------------------+`"

C4VC_TC_PRE = "🔒"
C4VC_TTC_SUF = "-ttc4vc"
C4VC_PTC_SUF = "-ptc4vc"
C4VC_ROLE_SUF = "-role4vc"

MAKE_TTC_COMMAND = "?transient"
MAKE_PTC_COMMAND = "?permanent"

DO_SEND_ESMSG = False	# If bot sends a message marking the end of the session in a PTC

client = Client(intents=Intents.all())

locks:dict = {}

#---------------------------------Functions------------------------------------

def printlvl(lvl:int, text:str):
	print("\t"*lvl + text)

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

def makeValidName(name:str) -> str :
	# Remove emojis
	pattern = re.compile(pattern = r"[^a-zA-Z0-9_ ]+", flags = re.UNICODE)
	newName = pattern.sub(r'', name)
	# Replace spaces with underscores
	newName = newName.replace(" ", "_")
	# OPTIONAL: Remove underscores at the begining
	while len(newName) >= 2 and newName[0] == "_":
		newName = newName[1:]
	# Transform into lowercase
	newName = newName.lower()
	return newName

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
	tc = await findTC(guild, vc.name)
	if tc != None:
		printlvl(lvl, f"Text channel '{makeValidName(tc.name)}' already exists")
		await tc.set_permissions(guild.default_role, send_messages=False, read_messages=False)
		await tc.set_permissions(role, send_messages=True, read_messages=True)
	else:
		ttcName = getTTCName(vc.name)
		printlvl(lvl, f"Creating text channel '{makeValidName(ttcName)}'")
		tc = await guild.create_text_channel(name=ttcName, category=vc.category)
		if tc == None:
			raise Exception("Couldn't create TC")
		await tc.set_permissions(guild.default_role, send_messages=False, read_messages=False)
		await tc.set_permissions(role, send_messages=True, read_messages=True)
		await tc.send(f"This text channel is private for people on the VC: {vc.name}\n"\
				+ f"This channel is currently **Transient**. " \
				+ f"You can change this by writing `{MAKE_PTC_COMMAND}` or `{MAKE_TTC_COMMAND}` in this channel")
	return tc

async def setupRoleAndTC(vc:VoiceChannel, lvl:int):
	vcValidName = makeValidName(vc)
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
		printlvl(lvl+1, f"Removing role '{role.name}' from '{makeValidName(member.name)}'")
		await member.remove_roles(role, reason="Resetting Role")
	for member in vc.members:
		printlvl(lvl+1, f"Adding role '{role.name}' to '{makeValidName(member.name)}'")
		await member.add_roles(role, reason="Resetting Role and User is in VC")

async def processUserLeave(vc:VoiceChannel, member:Member, lvl:int):
	guild = vc.guild
	vcName = vc.name

	printlvl(lvl, f"User '{makeValidName(member.name)}' left VC '{makeValidName(vcName)}'")
	role = findRole(guild, vcName)
	if role != None:
		await member.remove_roles(role, reason="User left VC")

	if len(vc.members) <= 0:
		await cleanUp(guild)
		# Check if the Role and TC exist, if not, create them
		tc = await findTC(guild, vcName)
		if role == None or tc == None:
			await setupRoleAndTC(vc, lvl=lvl)
			role = findRole(guild, vcName)
		# Check if the role has members, if it has, reset it since it shouldn't
		if len(role.members) > 0:
			await resetRoleMembers(vc, role, lvl=lvl)
		# Send a message to the TC marking the end of the Session
		if isTTC(tc.name):
			await tc.delete()
		if isPTC(tc.name) and DO_SEND_ESMSG:
			await tc.send(END_SESSION_MSG)

async def processUserJoin(vc:VoiceChannel, member:Member, lvl:int):
	vcName = vc.name

	printlvl(lvl, f"User '{member.name}' joined VC '{makeValidName(vcName)}'")
	role = findRole(vc.guild, vcName)
	tc = await findTC(vc.guild, vcName)
	if role == None or tc == None:
		await setupRoleAndTC(vc, lvl=lvl+1)
	await member.add_roles(role, reason="User joined VC")

async def makePermanentTC(tc:TextChannel):
	if isTTC(tc.name):
		await tc.edit(name=getPTCNameFromTTCName(tc.name))
		await tc.send("This text channel is now **Permanent**. It won't be deleted even if everyone leaves the VC.")
	elif isPTC(tc.name):
		await tc.send("This text channel is already permanent.")
	else:
		await tc.send("This text channel is not managed by C4VC.")

async def makeTransientTC(tc:TextChannel):
	if isPTC(tc.name):
		await tc.edit(name=getTTCNameFromPTCName(tc.name))
		await tc.send("This text channel is now **Transient**. It will be deleted if everyone leaves the VC.")
	elif isTTC(tc.name):
		await tc.send("This text channel is already transient.")
	else:
		await tc.send("This text channel is not managed by C4VC.")

async def cleanUp(guild:Guild):
	expectedTCNames = []
	expectedRoleNames = []

	for vc in guild.voice_channels:
		expectedTCNames += [getTTCName(vc.name), getPTCName(vc.name)]
		expectedRoleNames += [getRoleName(vc.name)]

	for tc in guild.text_channels:
		if re.search(pattern = rf"({C4VC_TTC_SUF}|{C4VC_PTC_SUF})$", string=tc.name) != None \
				and tc.name not in expectedTCNames:
			await tc.delete()

	for role in guild.roles:
		if re.search(pattern = rf"{C4VC_ROLE_SUF}$", string=role.name) != None \
				and role.name not in expectedRoleNames:
			await role.delete()

#----------------------------------Events--------------------------------------

@client.event
async def on_ready():
	for guild in client.guilds:
		print(f"Setting up guild: {guild.name}")
		for vc in guild.voice_channels:
			if len(vc.members) > 0:
				print(f"\tSetting up voice channel with valid name '{makeValidName(vc.name)}'")
				await setupRoleAndTC(vc, lvl=2)
	print(f"Finished setup. Logged in as {client.user}")

@client.event
async def on_voice_state_update(member:Member, before:VoiceState, after:VoiceState):
	print("\nDetected a voice state update")
	if (before.channel != None) and ((after.channel == None) or (after.channel.id != before.channel.id)):
		await processUserLeave(before.channel, member, lvl=1)
	if (after.channel != None) and ((before.channel == None) or (before.channel.id != after.channel.id)):
		await processUserJoin(after.channel, member, lvl=1)

@client.event
async def on_message(message:Message):
	tc = message.channel
	if message.author.bot:
		return
	if message.content.lower() == MAKE_TTC_COMMAND:
		await makeTransientTC(tc)
	if message.content.lower() == MAKE_PTC_COMMAND:
		await makePermanentTC(tc)

#-----------------------------Run and Connect Bot------------------------------

try:
	client.run('ODU3NjcwNDUwMTc1OTM0NTI0.YNS92g.muxqEFYWSsBHMQ7JUFpbfGNJ3qs')
except Exception as e:
	print(e)