@client.event
async def on_message(message):    
    if message.guild:
        guild_id = message.guild.id
        config = load_config(guild_id)
        if config["listen"] and message.author != client.user:
            guild_message_histories[guild_id].append({"role": "user", "content": process_msg(message)})
        history = guild_message_histories[guild_id]
        if not message.channel.permissions_for(message.guild.me).send_messages:
            return
    else:
        user_id = message.author.id
        userconfig = "userland"
        config = load_config(userconfig)
        if config["listen"] and message.author != client.user:
            dm_message_histories[user_id].append({"role": "user", "content": process_msg(message)})
        history = dm_message_histories[user_id]

    if message.author == client.user:
        history.append({"role": "assistant", "content": message.content})
        return # Ignore itself lol
    
    # --- BOT COMMANDS ---
    #:section src/commands/option.obun.py
    #:section src/commands/help.obun.py
    #:section src/commands/about.obun.py
    #:section src/commands/eval.obun.py
    #:section src/commands/address.obun.py
    #:section src/commands/trustuntrust.obun.py
    #:section src/commands/send.obun.py
    #:section src/commands/phonebook.obun.py
    #:section src/commands/dadjoke.obun.py
    #:section src/commands/owobonk.obun.py
    #:section src/commands/search.obun.py
    # ------------------
    
    if not config["listen"]:
        return
    
    should_respond = message.mention_everyone or client.user.mentioned_in(message) or random.random() < (config["responseFrequency"] / 100)
    should_reply = client.user.mentioned_in(message) or message.reference is not None
    
    if should_respond:
        async with message.channel.typing():
            num_responses = random.choices([1, 2], weights=[85, 15], k=1)[0]

            for i in range(num_responses):
                if random.random() < tin_can_chance:
                    if random.randint(0, 1) == 0:
                        response = "*tin can noises*"
                    else:
                        response = "https://odysea.us.to/assets/dump/iamarobot.mov"
                else:
                    #print('response' if i == 0 else 'continuation')
                    response = await generate_response(
                        'respond' if i == 0 else 'continue Rob\'s previous message',
                        history,
                        config.get("model"),
                        config.get("dumb"),
                        f"the {message.guild.name} server" if message.guild else "DMs"
                    )

                if (history and history[-1]["role"] == "assistant" and history[-1]["content"] == response):
                    continue

                if "[searchfor: " in response:
                    should_reply = False

                if should_reply and i == 0:
                    await message.reply(response,  mention_author=False)
                else:
                    if "[searchfor: " in response:
                        async def update_status(text):
                            await message.channel.send(text)

                        q = response[len("[searchfor:"): -1].strip()
                        result = await websearch(q, update_status)
                        response = await generate_response(
                            f"Summarize the following text so that it's relevant to the conversation: '{result}'. Use the amount of words necessary to make a detailed explanation.",
                            history,
                            config.get("model"),
                            config.get("dumb"),
                            f"the {message.guild.name} server" if message.guild else "DMs"
                        )
                        await message.channel.send(response)
                    else:
                        await message.channel.send(response)

                # sleep between responses, not after the last one
                if i < num_responses - 1:
                    await asyncio.sleep(random.uniform(0.5, 2))

        if message.guild:
            guild_daily_stats[message.guild.id] += num_responses
