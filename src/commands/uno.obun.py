    if message.content.startswith(f"{cmdprefix}uno") and message.guild:
        if message.channel.id in uno_matches:
            return await message.channel.send(
                content="there's an ongoing UNO match already!"
            )

        view = UnoLobbyView(message.author, message.channel)
        return await message.channel.send(embed=view.get_embed(), view=view)
