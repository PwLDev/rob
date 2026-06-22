    if message.content.startswith("#!search"):
        q = message.content.replace("#!search ", "")

        async def update_status(text):
            await message.channel.send(text)

        result = await websearch(q, update_status)
        response = await generate_response(
            f"Summarize the following text so that it's relevant to the conversation: '{result}'. Use the amount of words necessary to make a detailed explanation.",
            history,
            config.get("model"),
            config.get("dumb"),
            f"the {message.guild.name} server" if message.guild else "DMs"
        )
        await message.channel.send(response)
        return
