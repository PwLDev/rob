    if message.content.startswith("#!address") and message.guild:
        await message.channel.send(f"this server's address is `{guild_address(message.guild)}`")
        return
