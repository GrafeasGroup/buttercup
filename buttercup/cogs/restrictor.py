import copy
from typing import Any, Callable, Dict

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
        self.members.subscribe(self._set_access)

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
        """Restrict the new member and send them a welcome message."""
        await self._create_record(member)

    @Cog.listener()
    async def on_member_update(self, before: Member, after: Member) -> None:
        """
        Perform validation when a member is updated.

        This validation consists of checking whether the changed nickname is
        compliant with the set nickname constraints.
        """
        record = await self._get_record(after)
        if before.nick != after.nick:
            # The member's nickname is changed, validate it.
            record["nickname"] = self._correct_nickname(after.nick)
        await self.members.update(after, record)

    @command()
    async def accept(self, ctx: Context) -> None:
        """Allow the user to accept the Code of Conduct."""
        member = ctx.author
        record = await self._get_record(member)
        record["coc"] = True
        await self.members.update(member, record)
        await self._send_message(self.restrict_channel, "coc_accepted", member)

    @staticmethod
    def _correct_nickname(nickname: str) -> bool:
        """
        Whether a nickname is correct.

        This check is currently only based on whether the username starts with
        "/u/", but can be extended.
        """
        return nickname is not None and nickname.startswith("/u/")

    async def _set_access(
        self, member: Member, old: Dict[str, bool], new: Dict[str, bool]
    ) -> None:
        """
        Set the access of the provided member.

        Whether the user is allowed access or is restricted is determined by the
        saved values of the specific user. If they have met all constraints, they
        are allowed access. If this is not the case, they are restricted.
        """
        record = new
        if all(record.values()) and self.restrict_role in member.roles:
            await member.remove_roles(self.restrict_role)
            # This set difference is used since the roles sometimes still include
            # the previously removed role.
            if len(set(member.roles).difference({self.restrict_role})) <= 1:
                # Note that each user has the "@everyone" role.
                await member.add_roles(self.accepted_role)
                await self._send_message(
                    self.welcome_channel, "restriction_lifted", member
                )
        elif not record["nickname"]:
            await member.add_roles(self.restrict_role)
            if record["coc"]:
                await self._send_message(
                    self.restrict_channel, "wrong_username", member
                )
            else:
                await self._send_message(self.restrict_channel, "new_member", member)

    async def _get_record(self, member: Member) -> Dict[str, bool]:
        """Retrieve the record of the member, creating one if not yet available."""
        if member not in self.members.dictionary:
            await self._create_record(member)
        return self.members.get(member)

    async def _create_record(self, member: Member) -> Dict[str, bool]:
        """Create a record for the specified member."""
        nickname_check = self._correct_nickname(member.nick)
        # Assume the member has accepted the CoC if they have a role other than
        # the restriction role or the member has another role than the
        # restriction role and "@everyone"
        coc_check = self.restrict_role not in member.roles or len(member.roles) > 2
        return await self.members.update(
            member, {"nickname": nickname_check, "coc": coc_check}
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
