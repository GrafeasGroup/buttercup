from typing import Dict

import discord.utils
from discord.ext.commands import Cog, Context, command
from discord.member import Member
from discord.role import Role

from buttercup.bot import ButtercupBot


class NewMember(Cog):
    def __init__(
        self, bot: ButtercupBot, restrict_role: str, accepted_role: str,
    ) -> None:
        """Initialize the user dictionary and retrieve the relevant roles."""
        self.bot = bot
        self.members = dict()
        self.restrict_name = restrict_role
        self.accepted_name = accepted_role

    @property
    def restrict_role(self) -> Role:
        """Provide the restriction role based on the guild's roles."""
        return discord.utils.get(self.bot.guild.roles, name=self.restrict_name)

    @property
    def accepted_role(self) -> Role:
        """Provide the accepted role based on the guild's roles."""
        return discord.utils.get(self.bot.guild.roles, name=self.accepted_name)

    @Cog.listener()
    async def on_member_join(self, member: Member) -> None:
        """Restrict the new member and send them a welcome message."""
        record = self._get_record(member)
        if not all(record.values()):
            await member.add_roles(self.restrict_role)
            # TODO: Send welcome message.

    @Cog.listener()
    async def on_member_update(self, before: Member, after: Member) -> None:
        """
        Perform validation when a member is updated.

        This validation consists of checking whether the changed nickname is
        compliant with the set nickname constraints.
        """
        record = self._get_record(after)
        if before.nick != after.nick:
            # The member's nickname is changed, validate it.
            record["nickname"] = self._correct_nickname(after.nick)
        await self._set_access(after)

    @command()
    async def accept(self, ctx: Context) -> None:
        """Allow the user to accept the Code of Conduct."""
        member = ctx.author
        record = self._get_record(member)
        record["coc"] = True
        await self._set_access(member)

    @staticmethod
    def _correct_nickname(nickname: str) -> bool:
        """
        Whether a nickname is correct.

        This check is currently only based on whether the username starts with
        "/u/", but can be extended.
        """
        return nickname is not None and nickname.startswith("/u/")

    async def _set_access(self, member: Member) -> None:
        """
        Set the access of the provided member.

        Whether the user is allowed access or is restricted is determined by the
        saved values of the specific user. If they have met all constraints, they
        are allowed access. If this is not the case, they are restricted.
        """
        record = self._get_record(member)
        if all(record.values()) and self.restrict_role in member.roles:
            await member.remove_roles(self.restrict_role)
            # This set difference is used since the roles sometimes still include
            # the previously removed role.
            if len(set(member.roles).difference({self.restrict_role})) <= 1:
                # Note that each user has the "@everyone" role.
                await member.add_roles(self.accepted_role)
        elif not record["nickname"]:
            await member.add_roles(self.restrict_role)

    def _get_record(self, member: Member) -> Dict[str, bool]:
        """Retrieve the record of the member, creating one if not yet available."""
        if member not in self.members:
            nickname_check = self._correct_nickname(member.nick)
            # Assume the member has accepted the CoC if they have a role other than
            # the restriction role or the member has another role than the
            # restriction role and "@everyone"
            coc_check = self.restrict_role not in member.roles or len(member.roles) > 2
            self.members[member] = {"nickname": nickname_check, "coc": coc_check}
        return self.members[member]


def setup(bot: ButtercupBot) -> None:
    """Set up the NewMember cog."""
    cog_config = bot.config["NewMember"]
    restrict_name = cog_config.get("restrict_role", "New User")
    accepted_name = cog_config.get("accepted_role", "Visitor (0)")
    bot.add_cog(NewMember(bot, restrict_name, accepted_name))
