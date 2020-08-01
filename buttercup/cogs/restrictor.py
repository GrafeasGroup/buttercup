import copy
from typing import Any, Callable

import discord.utils
from discord.channel import TextChannel
from discord.ext.commands import Cog, Context, command
from discord.member import Member
from discord.role import Role

from buttercup.bot import ButtercupBot
from buttercup.strings import translation

i18n = translation()


class ObservableDict:
    def __init__(self) -> None:
        """Initialize the dictionary and a list of observers."""
        self.dictionary = dict()
        self.observers = list()

    async def update(self, key: Any, value: Any) -> Any:
        """Update the value for the key and notify the observers if its a new value."""
        old = self.dictionary.get(key)
        self.dictionary[key] = value
        if old != value:
            for observer in self.observers:
                await observer(key, old, value)
        return self.get(key)

    def get(self, key: Any) -> Any:
        """Retrieve a copy of the current saved value for the key."""
        return copy.deepcopy(self.dictionary.get(key))

    def subscribe(self, observer: Callable) -> None:
        """
        Subscribe the observer to changes made to the dictionary.

        An observer should be a callable with the following signature:
        callable(key: Any, old: Any, new: Any),
        where key is the key updated, old is the value before and new the value
        after updating.
        """
        self.observers.append(observer)


class Record:
    def __init__(
        self, nickname: str = None, coc: bool = False, restricted: bool = True
    ) -> None:
        """
        Initialize the user record.

        The record contains the following fields:
        - nickname: The nickname of the member
        - coc: Whether the member has accepted the Code of Conduct
        - restricted: Whether the member has restricted access to Discord
        - compliant: Whether the member complies with all set constraints
        - new_user: Whether the member is a new user
        - correct_nickname: Whether the member's nickname is correct
        """
        self.nickname = nickname
        self.coc = coc
        self.restricted = restricted

    @property
    def compliant(self) -> bool:
        """Whether the member complies with all set constraints."""
        return self.coc and self.correct_nickname

    @property
    def new_user(self) -> bool:
        """Whether the member is a new user."""
        return all([not self.coc, self.nickname is None])

    @property
    def correct_nickname(self) -> bool:
        """
        Whether a nickname is correct.

        This check is currently only based on whether the username starts with
        "/u/", but can be extended.
        """
        return self.nickname is not None and self.nickname.startswith("/u/")


class Restrictor(Cog):
    def __init__(
        self,
        bot: ButtercupBot,
        restrict_role: str,
        accepted_role: str,
        restrict_channel: str,
        welcome_channel: str,
    ) -> None:
        """Initialize the user dictionary and retrieve the relevant roles and channels."""
        self.bot = bot
        self.restrict_name = restrict_role
        self.accepted_name = accepted_role
        self.restrict_channel_name = restrict_channel
        self.welcome_channel_name = welcome_channel
        self.members = ObservableDict()
        self.members.subscribe(self._handle_update)

    @property
    def restrict_role(self) -> Role:
        """Provide the restriction role based on the guild's roles."""
        return discord.utils.get(self.bot.guild.roles, name=self.restrict_name)

    @property
    def accepted_role(self) -> Role:
        """Provide the accepted role based on the guild's roles."""
        return discord.utils.get(self.bot.guild.roles, name=self.accepted_name)

    @property
    def restrict_channel(self) -> TextChannel:
        """Provide the restricted channel based on the guild's text channels."""
        return discord.utils.get(
            self.bot.guild.text_channels, name=self.restrict_channel_name
        )

    @property
    def welcome_channel(self) -> TextChannel:
        """Provide the welcome channel based on the guild's text channels."""
        return discord.utils.get(
            self.bot.guild.text_channels, name=self.welcome_channel_name
        )

    @Cog.listener()
    async def on_member_join(self, member: Member) -> None:
        """Create a member record when they join the server."""
        await self._create_record(member)

    @Cog.listener()
    async def on_member_update(self, before: Member, after: Member) -> None:
        """Update the member record whenever their Discord profile changes."""
        record = await self._get_record(after)
        record.nickname = after.nick
        record.restricted = self.restrict_role in after.roles
        await self.members.update(after, record)

    @command()
    async def accept(self, ctx: Context) -> None:
        """Allow the member to accept the Code of Conduct."""
        member = ctx.author
        record = await self._get_record(member)
        record.coc = True
        await self.members.update(member, record)

    async def _handle_update(self, member: Member, old: Record, new: Record) -> None:
        """
        Handle the update of the member record.

        This method checks what actions have to be taken according to the update that
        has occurred. These actions include:
        - Restricting a non-compliant member
        - Unrestricting a compliant member
        - Notifying the member of a CoC acceptance update
        - Notifying the member of a nickname update, sending a message depending on
          the correctness of its format
        """
        channel = self.welcome_channel if new.compliant else self.restrict_channel
        first_time_user = len(set(member.roles).difference({self.restrict_role})) == 1
        if old is None and new.new_user:
            await member.add_roles(self.restrict_role)
            await self._send_message(channel, "new_member", member)
            return

        if new.restricted and new.compliant:
            # Remove restriction
            await member.remove_roles(self.restrict_role)
            if first_time_user:
                # They are unrestricted first time, welcome in channel.
                await self._send_message(channel, "new_lifted", member)
                await member.add_roles(self.accepted_role)
        if not new.restricted and not new.compliant:
            # Add restriction
            await member.add_roles(self.restrict_role)
            # await self._send_message(channel, "restricted", member)

        if old and old.coc != new.coc:
            # The member has accepted the CoC, send him a confirmation.
            await self._send_message(channel, "coc_accepted", member)
            pass

        if new.nickname and old is not None and old.nickname != new.nickname:
            # The nickname has changed from what we knew before.
            if new.correct_nickname:
                # Send confirmation that new nickname is correct.
                await self._send_message(channel, "correct_nick", member)
            elif new.nickname.startswith("u/"):
                # Send message explaining the common wrong prefix.
                await self._send_message(channel, "wrong_prefix", member)
            else:
                # Repeat the wrong nickname instructions.
                await self._send_message(channel, "wrong_nick", member)

    async def _get_record(self, member: Member) -> Record:
        """Retrieve the record of the member, creating one if not yet available."""
        if member not in self.members.dictionary:
            await self._create_record(member)
        return self.members.get(member)

    async def _create_record(self, member: Member) -> Record:
        """Create a record for the specified member."""
        # Assume the member has accepted the CoC if they do not have the
        # restriction role or the member has another role than the
        # restriction role and "@everyone"
        restricted_check = self.restrict_role in member.roles
        coc_check = not restricted_check or len(member.roles) > 2
        return await self.members.update(
            member,
            Record(nickname=member.nick, coc=coc_check, restricted=restricted_check),
        )

    @staticmethod
    async def _send_message(
        channel: TextChannel, message_name: str, member: Member
    ) -> None:
        """Send the specified message, formatted through the member, in the channel."""
        await channel.send(i18n["restrictor"][message_name].format(member.id))


def setup(bot: ButtercupBot) -> None:
    """Set up the NewMember cog."""
    cog_config = bot.config["Restrictor"]
    restrict_name = cog_config.get("restrict_role", "New User")
    accepted_name = cog_config.get("accepted_role", "Visitor (0)")
    restrict_channel = cog_config.get("restrict_channel", "new-user")
    welcome_channel = cog_config.get("welcome_channel", "off-topic")
    bot.add_cog(
        Restrictor(bot, restrict_name, accepted_name, restrict_channel, welcome_channel)
    )


def teardown(bot: ButtercupBot) -> None:
    """Unload the Restrictor cog."""
    bot.remove_cog("Restrictor")
