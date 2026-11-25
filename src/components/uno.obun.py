#:if DEBUG
import asyncio
import random
from selectors import DevpollSelector
from typing import Dict

import discord
from attr import dataclass

#:endif

UNO_COLORS = ["red", "green", "blue", "yellow"]
UNO_NUMBERS = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
UNO_SPECIALS = ["draw_two", "reverse", "skip"]
UNO_WILDS = ["draw_four", "wild"]
UNO_SQUARES = {"red": "🟥", "green": "🟩", "blue": "🟦", "yellow": "🟨"}
UNO_HELP = (
    "## how to play UNO!\n"
    "your goal is to be left with ZERO cards on your deck by stacking cards with same symbol or color!\n\n"
    "**cards** 📥 - displays the cards on your deck, if it's your turn shows a dropdown to play a card\n"
    "**draw** 📤 - draws a card from the pile, use if u dont have any matching card\n"
    "**UNO!** 🗣️ - says UNO! when u have ONE card left __(use it BEFORE playing your next card)__\n"
    "❌ - cancels the current match, only for the organizer\n"
    "note: you only have 30 seconds per turn, be quick!"
)

uno_matches: list[int] = []


@dataclass
class UnoCard:
    color: str
    value: str
    used: bool = False

    def emoji(self) -> str:
        if self.value in UNO_WILDS:
            return "🎨"
        return UNO_SQUARES.get(self.color, "❓")

    def render(self) -> str:
        return f"{self.emoji()} {self}"

    def __str__(self):
        name = self.value.split("_")[1] if self.value.startswith("any") else self.value
        if name == "draw_two":
            return "+2"
        elif name == "draw_four":
            return "+4"
        elif name == "wild":
            return "WILD"
        elif name == "reverse":
            return "🔁"
        elif name == "skip":
            return "🚫"
        return str(UNO_NUMBERS.index(name) + 1)


class UnoDeckMenu(discord.ui.Select):
    def __init__(
        self,
        view: discord.ui.View,
        author: discord.User | discord.Member,
        current: UnoCard,
        deck: list[UnoCard],
    ):
        self.author = author
        self.card = current
        self.deck = deck
        self.typed_view: UnoDeckView = view  # type: ignore

        options: list[discord.SelectOption] = []
        for i, card in enumerate(deck, start=0):
            option = discord.SelectOption(
                label=str(card), emoji=card.emoji(), value=str(i)
            )
            options.append(option)

        super().__init__(options=options[:25], placeholder="select a card to play it")

    def is_legal_movement(self, card: UnoCard) -> bool:
        if card.value in UNO_WILDS:
            return True
        # value `any` represents an internal metacard that accepts any card of the color chosen
        if self.card.value.startswith("any") and card.color == self.card.color:
            return True
        if card.value == self.card.value:
            return True
        return card.color == self.card.color

    async def callback(self, interaction: discord.Interaction):
        selected = int(self.values[0])
        card = self.deck[selected]

        if not self.is_legal_movement(card):
            return await interaction.response.edit_message(
                content="hmm that doesn't fit :/\nthe cards has to be the same color or number as the last one, or use a WILD or +4 card",
                view=self.typed_view,
            )

        self.typed_view.selected = selected
        self.typed_view.stop()
        return await interaction.response.defer()


class UnoDeckView(discord.ui.View):
    def __init__(
        self,
        author: discord.User | discord.Member,
        current: UnoCard,
        deck: list[UnoCard],
    ):
        super().__init__(timeout=30)
        self.author = author
        self.deck = deck
        self.selected: int | None = None
        self.add_item(UnoDeckMenu(self, author, current, deck))

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True  # type: ignore

    async def interaction_check(self, interaction):
        return interaction.user.id == self.author.id


class UnoColorView(discord.ui.View):
    def __init__(
        self,
        author: discord.User | discord.Member | discord.ClientUser,
        channel: discord.TextChannel,
    ):
        super().__init__(timeout=30)
        self.author = author
        self.channel = channel
        self.result = UNO_COLORS[
            random.randint(0, len(UNO_COLORS) - 1)
        ]  # choose random if timeout

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True  # type: ignore
        await self.channel.send(
            content=f"no response, the new color is **{self.result}**! {UNO_SQUARES.get(self.result, '')}"
        )

    async def interaction_check(self, interaction):
        return interaction.user.id == self.author.id

    async def submit_colour(
        self, interaction: discord.Interaction[discord.Client], index: int
    ):
        self.result = UNO_COLORS[index]
        for i, child in enumerate(self.children):
            if i == index:
                child.style = discord.ButtonStyle.primary  # type: ignore
            child.disabled = True  # type: ignore

        await interaction.response.edit_message(view=self)

        self.stop()
        await asyncio.sleep(5)
        return await interaction.delete_original_response()

    @discord.ui.button(emoji="🟥", style=discord.ButtonStyle.secondary)
    async def red_button(self, interaction: discord.Interaction, button):
        return await self.submit_colour(interaction, 0)

    @discord.ui.button(emoji="🟩", style=discord.ButtonStyle.secondary)
    async def green_button(self, interaction: discord.Interaction, button):
        return await self.submit_colour(interaction, 1)

    @discord.ui.button(emoji="🟦", style=discord.ButtonStyle.secondary)
    async def blue_button(self, interaction: discord.Interaction, button):
        return await self.submit_colour(interaction, 2)

    @discord.ui.button(emoji="🟨", style=discord.ButtonStyle.secondary)
    async def yellow_button(self, interaction: discord.Interaction, button):
        return await self.submit_colour(interaction, 3)


class UnoView(discord.ui.View):
    def __init__(
        self,
        author: discord.User | discord.Member,
        channel: discord.TextChannel,
        players: list[discord.User | discord.Member | discord.ClientUser],
    ):
        super().__init__(timeout=None)
        self.author = author
        self.channel = channel

        # Game properties
        self.count = 1  # keep track of how many movements we had
        self.events: list[str] = []
        self.decks: Dict[int, list[UnoCard]] = {}
        self.played = asyncio.Event()
        self.current_card = self.get_random_card()
        self.current_turn = 0
        self.running = True
        self.inactivity = 0
        self.players = players

        # If special, reroll until we get a number card to begin
        while self.current_card.value not in UNO_NUMBERS:
            self.current_card = self.get_random_card()

        # Give players their deck of cards
        random.shuffle(self.players)
        for player in players:
            self.decks[player.id] = []
            player_deck = self.decks[player.id]
            for i in range(7):  # 7 initial cards
                player_deck.append(self.get_random_card())

        # Begin the main loop
        self.task = asyncio.create_task(self.main_loop())

    async def interaction_check(
        self, interaction: discord.Interaction[discord.Client]
    ) -> bool:
        if not self.channel.id in uno_matches:
            for child in self.children:
                child.disabled = True  # type: ignore
            await interaction.response.send_message(
                content=f"sry, that match is not active anymore ;(\nu can begin a new one with {cmdprefix}uno",
                ephemeral=True,
            )
            return False
        return True

    async def end_game(self):
        self.running = False
        for child in self.children:
            child.disabled = True  # type: ignore
        uno_matches.pop(uno_matches.index(self.channel.id))
        self.stop()

    def get_embed(self) -> discord.Embed:
        turn = self.players[self.current_turn]
        render_name = (
            f"{turn.display_name}'"
            if turn.display_name.endswith("s")
            else f"{turn.display_name}'s"
        )
        output_turns = []
        for i, player in enumerate(self.players):
            if player.id == turn.id:
                output_turns.append(f"**{player.display_name}**")
            else:
                output_turns.append(player.display_name)

        desc = (
            f"current card: {self.current_card.emoji()} {self.current_card}\n"
            f"turns: {', '.join(output_turns)}"
        )
        if self.current_card.used and self.current_card.value in UNO_WILDS:
            desc += f"\nselected color: **{self.current_card.color}** {UNO_SQUARES.get(self.current_card.color, '')}"

        embed = discord.Embed(
            title=f"UNO! - {render_name} turn",
            description=desc,
            colour=0xED4245,
        )

        image_dir = (
            "special"
            if self.current_card.value in UNO_WILDS
            else self.current_card.color
        )

        # odysea hosts the uno card images
        image_url = f"https://odysea.us.to/assets/dump/rob/uno/{image_dir}/{self.current_card.value}.png"
        if self.current_card.value.startswith("any"):
            image_url = f"https://odysea.us.to/assets/dump/rob/uno/special/{self.current_card}.png"

        embed.set_image(url=image_url)
        embed.set_footer(text=f"interactive UNO! - move #{self.count}")

        return embed

    # This is not 100% accurate but tries to keep it fair based on a regular 108 card deck
    def get_random_card(self) -> UnoCard:
        card_value: str = ""
        color = UNO_COLORS[random.randint(0, len(UNO_COLORS) - 1)]
        chance = random.randint(0, 100)

        if chance < 25:  # special chance (real is 29.63%)
            if chance < 10:  # wild chance (real is 7.41%)
                card_value = UNO_WILDS[random.randint(0, len(UNO_WILDS) - 1)]
            else:
                card_value = UNO_SPECIALS[random.randint(0, len(UNO_SPECIALS) - 1)]
        else:  # regular number card
            card_value = UNO_NUMBERS[random.randint(0, len(UNO_NUMBERS) - 1)]

        return UnoCard(color, card_value)

    def is_legal_movement(self, card: UnoCard) -> bool:
        if card.value in UNO_WILDS:
            return True
        # value `any` represents an internal metacard that accepts any card of the color chosen
        if (
            self.current_card.value.startswith("any")
            and card.color == self.current_card.color
        ):
            return True
        if card.value == self.current_card.value:
            return True
        return card.color == self.current_card.color

    async def main_loop(self):
        await asyncio.sleep(1)
        message = await self.channel.send(embed=self.get_embed(), view=self)
        first_time = True

        while self.running:
            turn = self.players[self.current_turn]
            deck = self.decks[turn.id]
            last_amount = len(deck)
            self.played.clear()

            if first_time:
                first_time = False
            else:
                await message.edit(
                    content="\n".join(self.events), embed=self.get_embed(), view=self
                )
                self.events.clear()

            if turn.bot:  # it must be rob im lazy to actually check
                await asyncio.sleep(random.randint(3, 5))  # rob thinking
                legal_moves = list(filter(self.is_legal_movement, deck))
                if len(legal_moves) > 0:
                    # play a random legal move
                    card = legal_moves[random.randint(0, len(legal_moves) - 1)]
                    self.current_card = card
                    deck.pop(deck.index(card))
                else:
                    # draw card
                    self.events.append("i drew a card from the pile!")
                    deck.append(self.get_random_card())

                if len(deck) == 1:
                    if random.randint(0, 100) > 5:  # 5% chance rob forgets to say uno
                        for i in range(2):
                            self.decks[turn.id].append(self.get_random_card())
                        self.events.append(
                            "whoops, i forgot to say UNO! i drew two cards"
                        )
                    else:
                        self.events.append("hehe i say UNO!!!")
            else:
                render_name = (
                    f"{turn.display_name}'"
                    if turn.display_name.endswith("s")
                    else f"{turn.display_name}'s"
                )

                try:  # wait for the user to play
                    await asyncio.wait_for(self.played.wait(), timeout=30)
                    self.inactivity = 0

                    if len(deck) > last_amount:  # they drew a card
                        self.events.append(
                            f"**{turn.display_name}** drew a card from the pile!"
                        )

                    # time to say UNO! if the user forgets draw two cards
                    if len(deck) == 1:
                        try:  # wait for the user to play
                            await asyncio.wait_for(self.played.wait(), timeout=5)
                            self.events.append(f"{turn.display_name} says **UNO!!!***")
                        except asyncio.TimeoutError:
                            for i in range(2):
                                self.decks[turn.id].append(self.get_random_card())
                            self.events.append(
                                f"**{turn.display_name}** forgot to say UNO!! they draw two cards"
                            )
                except asyncio.TimeoutError:
                    self.inactivity += 1
                    if self.inactivity > 5:
                        self.running = False
                        await self.channel.send(
                            content="this UNO match has been canceled after 5 inactivity strikes :/"
                        )
                        await self.end_game()
                    else:
                        deck.append(self.get_random_card())
                        self.events.append(
                            f"oops! time's up for **{turn.display_name}**, they drew a card"
                        )

            # at this point self.current_card will be holding the new card
            next_turn = (self.current_turn + 1) % len(self.players)
            next_user = self.players[next_turn]

            # process special cards ONLY ONCE
            if not self.current_card.used:
                if self.current_card.value in UNO_WILDS:
                    if self.current_card.value == "draw_four":
                        for i in range(4):
                            self.decks[next_user.id].append(self.get_random_card())
                        if next_user.bot:  # bot message
                            self.events.append("aw hell naww, i draw four cards")
                        else:
                            self.events.append(
                                f"**{next_user.display_name}**, u draw four cards!"
                            )

                    # here now
                    await message.edit(
                        content="\n".join(self.events),
                        embed=self.get_embed(),
                        view=self,
                    )

                    if turn.bot:  # the bot chooses a new color
                        colors = [x.color for x in deck]
                        choice = max(colors, key=colors.count)  # most common occurance

                        self.events.append(
                            f"hmm, i'm choosing color **{choice}** {UNO_SQUARES.get(choice, '')}"
                        )
                        self.current_card = UnoCard(choice, self.current_card.value)
                        await asyncio.sleep(2)
                    else:
                        view = UnoColorView(turn, self.channel)
                        await self.channel.send(
                            content=f"**{turn.display_name}**, choose a color!",
                            view=view,
                        )
                        await view.wait()
                        self.current_card = UnoCard(
                            view.result, self.current_card.value
                        )
                        self.events.append(
                            f"{turn.display_name} has chosen the color **{view.result}**! {UNO_SQUARES.get(view.result, '')}"
                        )

                    offset = 2 if self.current_card.value == "draw_four" else 1
                    self.current_turn = (self.current_turn + offset) % len(
                        self.players
                    )  # skip
                else:
                    if self.current_card.value == "draw_two":
                        for i in range(2):
                            self.decks[next_user.id].append(self.get_random_card())
                        if next_user.bot:  # bot message
                            self.events.append("aw man, i draw two cards")
                        else:
                            self.events.append(
                                f"**{next_user.display_name}**, u draw two cards!"
                            )
                        self.current_turn = (self.current_turn + 2) % len(
                            self.players
                        )  # skip
                    elif self.current_card.value == "reverse":
                        self.events.append(f"**{turn.display_name}** played reverse!!")
                        self.players.reverse()
                        self.current_turn = (self.players.index(turn) + 1) % len(
                            self.players
                        )  # reverse
                    elif self.current_card.value == "skip":
                        render_name = (
                            f"{next_user.display_name}'"
                            if next_user.display_name.endswith("s")
                            else f"{next_user.display_name}'s"
                        )
                        if next_user.bot:
                            self.events.append("i've been blocked :sob:")
                        else:
                            self.events.append(
                                f"{turn.display_name} blocked **{render_name}** turn!! sry bro"
                            )
                        self.current_turn = (self.current_turn + 2) % len(
                            self.players
                        )  # skip
                    else:
                        # next turn
                        self.current_turn = next_turn

                # avoid further usage of specials
                if self.current_card.value not in UNO_NUMBERS:
                    self.current_card.used = True
            else:
                self.current_turn = next_turn  # normal skip

            # increment the counter
            self.count += 1

            # check if this user wins
            if len(self.decks[turn.id]) < 1:
                self.running = False

        winner = self.players[(self.current_turn - 1) % len(self.players)]
        await self.end_game()
        await message.edit(
            embed=self.get_embed(),
            view=self,
        )
        if winner.bot:
            await self.channel.send(
                "## ggez i win :tada:\nsee? i'm the best at playing uno",
            )
        else:
            await self.channel.send(
                f"## gg {winner.display_name} :tada:\nu win this uno game, congrats!! :D",
            )

    @discord.ui.button(label="cards", style=discord.ButtonStyle.primary)
    async def play_button(
        self,
        interaction: discord.Interaction[discord.Client],
        button: discord.ui.Button,
    ):
        turn = self.players[self.current_turn]
        if interaction.user.id != turn.id:
            your_deck = self.decks[interaction.user.id]
            texts = [f"**your current deck** ({len(your_deck)})"]
            for card in your_deck:
                same = [
                    x
                    for x in your_deck
                    if x.value in UNO_WILDS
                    or (x.color == card.value and x.value == card.value)
                ]
                multiplier = f"(x{len(same)})" if len(same) > 1 else ""
                text = f"- {card.emoji()} {card} {multiplier}"
                if text not in texts:
                    texts.append(text)

            return await interaction.response.send_message(
                content="\n".join(texts),
                ephemeral=True,
            )

        deck = self.decks[turn.id]
        view = UnoDeckView(interaction.user, self.current_card, deck)

        await interaction.response.send_message(
            content=f"you currently have {len(deck)} cards on your deck",
            view=view,
            ephemeral=True,
        )
        await view.wait()

        if view.selected is not None:
            # they might have submitted just after the turn expires
            new_turn = self.players[self.current_turn]
            if interaction.user.id != new_turn.id:
                await interaction.followup.send(
                    content="oops, it's not ur turn anymore",
                    view=view,
                    ephemeral=True,
                )

            if not self.is_legal_movement(deck[view.selected]):
                await interaction.followup.send(
                    content="heyyy, that is an illegal movement, pls dont cheat... :P",
                    view=view,
                    ephemeral=True,
                )

            # place card and only after remove from the deck
            self.current_card = deck[view.selected]
            deck.pop(view.selected)

            # signal played
            self.played.set()
            return await interaction.delete_original_response()

    @discord.ui.button(label="draw", style=discord.ButtonStyle.primary)
    async def draw_button(
        self,
        interaction: discord.Interaction[discord.Client],
        button: discord.ui.Button,
    ):
        turn = self.players[self.current_turn]
        deck = self.decks[turn.id]

        if interaction.user.id != turn.id:
            return await interaction.response.send_message(
                content="wait! it's not ur turn yet, be patient :P", ephemeral=True
            )

        card = self.get_random_card()
        deck.append(card)

        self.played.set()
        return await interaction.response.send_message(
            content=f"you got: {card.emoji()} {card}",
            ephemeral=True,
        )

    @discord.ui.button(label="UNO!", style=discord.ButtonStyle.danger)
    async def say_button(
        self,
        interaction: discord.Interaction[discord.Client],
        button: discord.ui.Button,
    ):
        turn = self.players[self.current_turn]
        deck = self.decks[turn.id]

        if interaction.user.id != turn.id:
            return await interaction.response.send_message(
                content="wait! it's not ur turn yet, be patient :P", ephemeral=True
            )

        if len(deck) > 1:
            return await interaction.response.send_message(
                content="umm uno means one, u still have more than one card on your deck!",
                ephemeral=True,
            )

        self.played.set()
        return await interaction.response.send_message(
            content="you now said UNO!", ephemeral=True
        )

    @discord.ui.button(emoji="❓", style=discord.ButtonStyle.secondary)
    async def help_button(
        self,
        interaction: discord.Interaction[discord.Client],
        button: discord.ui.Button,
    ):
        return await interaction.response.send_message(content=UNO_HELP, ephemeral=True)

    @discord.ui.button(emoji="❌", style=discord.ButtonStyle.secondary)
    async def cancel_button(
        self,
        interaction: discord.Interaction[discord.Client],
        button: discord.ui.Button,
    ):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(
                content="only the organizer of the match can end the game!",
                ephemeral=True,
            )

        if not self.task.done():
            self.task.cancel()

        await self.end_game()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)
        await interaction.followup.send(
            content="the match organizer has ended this match ;("
        )


class UnoLobbyQuitView(discord.ui.View):
    def __init__(self, author: discord.User | discord.Member):
        super().__init__(timeout=30)
        self.author = author
        self.result = False

    async def interaction_check(self, interaction):
        return interaction.user.id == self.author.id

    @discord.ui.button(label="leave?", style=discord.ButtonStyle.danger)
    async def leave_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.edit_message(content="u quitted the uno match ;(")

        self.result = True
        button.disabled = True
        return self.stop()


class UnoLobbyView(discord.ui.View):
    def __init__(
        self, author: discord.User | discord.Member, channel: discord.TextChannel
    ):
        super().__init__(timeout=600)
        self.author = author
        self.channel = channel
        self.players: list[discord.User | discord.Member | discord.ClientUser] = [
            author
        ]
        uno_matches.append(self.channel.id)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True  # type: ignore

        await self.channel.send(
            content="the UNO match has been canceled due to inactivity ;("
        )
        uno_matches.pop(uno_matches.index(self.channel.id))

    def get_embed(self) -> discord.Embed:
        names = [x.display_name for x in self.players]
        embed = discord.Embed(
            title="UNO!",
            description=(
                "join the fully interactive classic UNO card game!!\n"
                "click the button to join in :D\n"
                "i can also play myself if u invite me btw :3\n\n"
                f"**players:** {', '.join(names)} ({len(self.players)}/10)"
            ),
            colour=0xED4245,
        )
        embed.set_footer(text="original game by Mattel, inc.")

        return embed

    @discord.ui.button(label="join!", style=discord.ButtonStyle.primary)
    async def join_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id == self.author.id:
            return await interaction.response.send_message(
                content="as the organizer u can't leave! instead u can finish the match with the red button",
                ephemeral=True,
            )

        if len(self.players) >= 10:
            return await interaction.response.send_message(
                content="sry, the game is already full ;(", ephemeral=True
            )

        user_ids = [k.id for k in self.players]
        if interaction.user.id in user_ids:  # user already joined
            quit = UnoLobbyQuitView(interaction.user)
            await interaction.followup.send(
                content="u already joined the game! :D",
                ephemeral=True,
                view=quit,
            )

            await quit.wait()
            if quit.result:
                for i, user in enumerate(self.players):
                    if user.id == interaction.user.id:
                        self.players.pop(i)
                        break
        else:  # user not joined
            self.players.append(interaction.user)
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
            return await interaction.followup.send(
                content="you're in! :D", ephemeral=True
            )

    @discord.ui.button(label="start", style=discord.ButtonStyle.success)
    async def start_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(
                content="only the organizer of the match can start the game!",
                ephemeral=True,
            )

        if len(self.players) < 2:
            return await interaction.response.send_message(
                content="u need at least 2 players to begin!\n-# psst, i can play myself too! click the tin can button :D",
                ephemeral=True,
            )

        for child in self.children:
            child.disabled = True  # type: ignore

        await interaction.response.edit_message(view=self)
        await interaction.followup.send(content="let the match begin!!")

        UnoView(self.author, self.channel, self.players)
        return self.stop()

    @discord.ui.button(emoji="🥫", style=discord.ButtonStyle.secondary)
    async def rob_button(
        self,
        interaction: discord.Interaction[discord.Client],
        button: discord.ui.Button,
    ):
        if not interaction.client.user:
            return await interaction.response.send_message(
                content="oops, i can't get in because of an error! D:",
                ephemeral=True,
            )

        user_ids = [k.id for k in self.players]
        if interaction.client.user.id in user_ids:
            return await interaction.response.send_message(
                content="i'm already in! thx for the invite :3",
                ephemeral=True,
            )
        else:
            button.disabled = True
            self.players.append(interaction.client.user)
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
            return await interaction.followup.send(
                content=f"i joined the match, yippee!!\nthx **{interaction.user.name}** for inviting :D"
            )

    @discord.ui.button(emoji="❓", style=discord.ButtonStyle.secondary)
    async def help_button(
        self,
        interaction: discord.Interaction[discord.Client],
        button: discord.ui.Button,
    ):
        return await interaction.response.send_message(content=UNO_HELP, ephemeral=True)

    @discord.ui.button(emoji="✖", style=discord.ButtonStyle.danger)
    async def cancel_button(
        self,
        interaction: discord.Interaction[discord.Client],
        button: discord.ui.Button,
    ):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message(
                content="only the organizer of the match can end the game!",
                ephemeral=True,
            )

        for item in self.children:
            item.disabled = True  # type: ignore

        await interaction.response.edit_message(embed=self.get_embed(), view=self)
        await interaction.followup.send(
            content="the match organizer has ended this match ;("
        )
        return self.stop()
