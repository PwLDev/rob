    if message.content.startswith("#!about") and message.guild:
        ranked = []
        reset_stats()

        await message.channel.send(f"haiiiii im rob, a conversational bot created by `dogo6647` :)")
        await message.channel.send(f"im currently in {len(client.guilds)} servers and have met {sum(g.member_count for g in client.guilds)} users, isnt that cool? :D")

        this_guild_msgs = guild_daily_stats[message.guild.id]
        for guild in client.guilds:
            if "COMMUNITY" not in guild.features:
                continue
            if guild.member_count <= 50:
                continue
            msg_count = guild_daily_stats[guild.id]
            ranked.append((guild.name, guild.member_count, msg_count))

        ranked.sort(key=lambda x: x[2], reverse=True)
        top_10 = ranked[:10]

        if top_10:
            top_servers = "\n".join(f"{i+1}. {name} ({members} members) - {msgs} interactions today" for i, (name, members, msgs) in enumerate(top_10))
            await message.channel.send(f"i've sent {this_guild_msgs} messages in this server today, heres today's biggest rob addicts:\n```{top_servers}```")
        return
