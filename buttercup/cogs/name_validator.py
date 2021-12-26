import re
from typing import Optional

from discord import Forbidden, TextChannel
from discord.ext.commands import Cog
from discord.member import Member

from buttercup import logger
from buttercup.bot import ButtercupBot
from buttercup.strings import translation

i18n = translation()


username_regex = re.compile(r"^(?P<leading_slash>/)?u/(?P<username>\S+)(?P<rest>.+)$")


class NameValidator(Cog):
    def __init__(self, bot: ButtercupBot, verified_role_id: str,) -> None:
        """Initialize the member's records and retrieve the roles and channels."""
        self.bot = bot
        self.verified_role_id = verified_role_id

    @Cog.listener()
    async def on_member_update(self, before: Member, after: Member) -> None:
        """Check whether the new nickname corresponds to the guidelines."""
        before_name = before.display_name
        after_name = after.display_name

        if before_name == after_name:
            # Only handle nickname changes
            return

        welcome_channel: Optional[TextChannel] = after.guild.system_channel
        verified_role = (
            after.guild.get_role(int(self.verified_role_id))
            if self.verified_role_id
            else None
        )

        if verified_role is None:
            logger.warning("No verified role defined. Can't validate nicknames!")
            return
        if welcome_channel is None:
            logger.warning("No welcome channel defined. Can't validate nicknames!")

        after_match = username_regex.search(after_name)
        if after_match is None:
            # Invalid nickname, remove the verified role
            await after.remove_roles(verified_role, reason="Invalid nickname")
            await welcome_channel.send(
                content=i18n["name_validator"]["invalid_name"].format(user_id=after.id)
            )
            return

        leading_slash = after_match.group("leading_slash")
        username = after_match.group("username")
        rest = after_match.group("rest")

        if leading_slash is None:
            # The user forgot the forward slash, fix it for them
            try:
                await after.edit(
                    reason="Add leading slash to server nickname",
                    nick=f"/u/{username}{rest}".strip(),
                )
            except Forbidden:
                # The user is a mod, can't fix the nickname
                await welcome_channel.send(
                    content=i18n["name_validator"][
                        "missing_slash_missing_permissions"
                    ].format(user_id=after.id, username=username)
                )
            # The edit will trigger another event.
            # To avoid duplicate messages we don't do anything here
            return

        before_match = username_regex.search(before_name)

        if before_match and before_match.group("leading_slash"):
            # The username was correct already and is still correct
            # For example timezone change, we don't have to send a message
            # Still set the role, just to be safe
            await after.add_roles(verified_role, reason="Correct nickname")
            return

        # The username was wrong, but is correct now
        await after.add_roles(verified_role, reason="Correct nickname")
        await welcome_channel.send(
            content=i18n["name_validator"]["valid_name"].format(
                user_id=after.id, username=username
            )
        )


def setup(bot: ButtercupBot) -> None:
    """Set up the NameValidator cog."""
    cog_config = bot.config["NameValidator"]
    verified_role_id = cog_config.get("verified_role_id")
    bot.add_cog(NameValidator(bot, verified_role_id))


def teardown(bot: ButtercupBot) -> None:
    """Unload the NameValidator cog."""
    bot.remove_cog("NameValidator")
