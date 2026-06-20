    if message.content.startswith("#!eval") and str(message.author.id) == str(OWNER_ID):
        await message.channel.send(exec(message.content.replace('#!eval ', '')))
