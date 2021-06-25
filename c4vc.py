#"Application ID" 		857670450175934524
#"Token"				ODU3NjcwNDUwMTc1OTM0NTI0.YNS92g.muxqEFYWSsBHMQ7JUFpbfGNJ3qs
#"Permissions Integer"	8

#R2K guild.id 			131480252500279296

#URL for invite			https://discordapp.com/oauth2/authorize?client_id=857670450175934524&scope=bot&permissions=8

#Compile to exe			pyinstaller chat4voicecall.py -F

from discord import *
import re

#-----------------------Initiate all global variables--------------------------
END_SESSION_MSG = \
	  "`+------------------------------------+`" + "\n" \
	+ "`|           END OF SESSION           |`" + "\n" \
	+ "`+------------------------------------+`"

C4VC_ROLE_SUF = "_c4vcr"
C4VC_TC_SUF = "_c4vct"

client = Client(intents=Intents.all())
#---------------------------------Functions------------------------------------

def printlvl(lvl:int, text:str):
	print("\t"*lvl + text)
#

def getRoleName(vcName:str) -> str :
	return makeValidName(vcName) + C4VC_ROLE_SUF
#

def getTCName(vcName:str) -> str :
	return makeValidName(vcName) + C4VC_TC_SUF
#

def findRole(guild:Guild, roleName:str) -> Role or None :
	for role in guild.roles:
		if role.name == roleName:
			return role
		#
	#
	return None
#

def findTC(guild:Guild, tcName:str) -> TextChannel or None :
	for tc in guild.text_channels:
		if tc.name == tcName:
			return tc
		#
	#
	return None
#

def makeValidName(name:str) -> str :
	# Remove emojis
	pattern = re.compile(pattern = "[^a-zA-Z0-9_ ]+", flags = re.UNICODE)
	newName = pattern.sub(r'', name)
	# Replace spaces with underscores
	newName = newName.replace(" ", "_")
	# OPTIONAL: Remove underscores at the begining
	while len(newName) >= 2 and newName[0] == "_":
		newName = newName[1:]
	#
	# Transform into lowercase
	newName = newName.lower()
	return newName
#

async def setupRole(vc:VoiceChannel, lvl:int) -> Role :
	guild = vc.guild
	roleName = getRoleName(vc.name)
	role = findRole(guild, roleName)
	if role != None:
		printlvl(lvl, f"Role '{roleName}' already exists.")
		await resetRoleMembers(vc, role, lvl=lvl+1)
	else:
		printlvl(lvl, f"Creating role '{roleName}'")
		role = await guild.create_role(name=roleName)
		if role == None:
			raise Exception("Couldn't create role")
		#
	#
	return role
#

async def setupTC(vc:VoiceChannel, role:Role, lvl:int) -> TextChannel :
	guild = vc.guild
	tcName = getTCName(vc.name)
	tc = findTC(guild, tcName)
	if tc != None:
		printlvl(lvl, f"Text channel '{tcName}' already exists")
	else:
		printlvl(lvl, f"Creating text channel '{tcName}'")
		tc = await guild.create_text_channel(name=tcName, category=vc.category, position=vc.position)
		if tc == None:
			raise Exception("Couldn't create TC")
	#
	await tc.set_permissions(guild.default_role, send_messages=False, read_messages=False)
	await tc.set_permissions(role, send_messages=True, read_messages=True)
	return tc
#

async def setupRoleAndTC(vc:VoiceChannel, lvl:int):
	role = await setupRole(vc, lvl=lvl)
	await setupTC(vc, role, lvl=lvl)
#

async def resetRoleMembers(vc:VoiceChannel, role:Role, lvl:int):
	printlvl(lvl, f"Resetting members of role '{role.name}'")
	for member in role.members:
		printlvl(lvl+1, f"Removing role '{role.name}' from '{member.name}'")
		await member.remove_roles(role, reason="Resetting Role")
	#
	for member in vc.members:
		printlvl(lvl+1, f"Adding role '{role.name}' to '{member.name}'")
		await member.add_roles(role, reason="Resetting Role and User is in VC")
	#
#

async def processUserLeave(vc:VoiceChannel, member:Member, lvl:int):
	guild = vc.guild
	vcName = vc.name

	printlvl(lvl, f"User '{member.name}' left VC '{makeValidName(vcName)}'")
	role = findRole(guild, getRoleName(vcName))
	if role != None:
		await member.remove_roles(role, reason="User left VC")
	#

	if len(vc.members) <= 0:
		# Check if the Role and TC exist, if not, create them
		tc = findTC(guild, getTCName(vcName))
		if role == None or tc == None:
			await setupRoleAndTC(vc, lvl=lvl)
			role = findRole(guild, getRoleName(vcName))
		#
		# Check if the role has members, if it has, reset it since it shouldn't
		if len(role.members) > 0:
			await resetRoleMembers(vc, role, lvl=lvl)
		#
		# Send a message to the TC marking the end of the Session
		# await tc.send(END_SESSION_MSG)
	#
#

async def processUserJoin(vc:VoiceChannel, member:Member, lvl:int):
	vcName = vc.name

	printlvl(lvl, f"User '{member.name}' joined VC '{makeValidName(vcName)}'")
	role = findRole(vc.guild, getRoleName(vcName))
	tc = findTC(vc.guild, getTCName(vcName))
	if role == None or tc == None:
		await setupRoleAndTC(vc, lvl=lvl+1)
	#
	await member.add_roles(role, reason="User joined VC")
#

def cleanUp(guild:Guild):
	expectedTCNames = []
	expectedRoleNames = []
	for vc in guild.voice_channels:
		expectedTCNames += [getTCName(vc.name)]
		expectedRoleNames += [getRoleName(vc.name)]
	#
	pattern = re.compile(pattern = f"*{C4VC_TC_SUF}$")
	for tc in guild.text_channels:
		if pattern.fullmatch(tc.name) and tc.name not in expectedTCNames:
			tc.delete()
		#
	#
	pattern = re.compile(pattern = f"*{C4VC_ROLE_SUF}$")
	for role in guild.roles:
		if pattern.fullmatch(role.name) and role.name not in expectedRoleNames:
			role.delete()
		#
	#
#

#----------------------------------Events--------------------------------------
@client.event
async def on_ready():
	for guild in client.guilds:
		print(f"Setting up guild: {guild.name}")
		for vc in guild.voice_channels:
			print(f"\tSetting up voice channel with valid name '{makeValidName(vc.name)}'")
			await setupRoleAndTC(vc, lvl=2)
		#
	#
	print(f"Finished setup. Logged in as {client.user}")
#

@client.event
async def on_voice_state_update(member:Member, before:VoiceState, after:VoiceState):
	print("\nDetected a voice state update")
	if (before.channel != None) and ((after.channel == None) or (after.channel.id != before.channel.id)):
		await processUserLeave(before.channel, member, lvl=1)
	#
	if (after.channel != None) and ((before.channel == None) or (before.channel.id != after.channel.id)):
		await processUserJoin(after.channel, member, lvl=1)
	#
#

#-----------------------------Run and Connect Bot------------------------------

try:
	client.run('ODU3NjcwNDUwMTc1OTM0NTI0.YNS92g.muxqEFYWSsBHMQ7JUFpbfGNJ3qs')
except Exception as e:
	print(e)