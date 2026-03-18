"""
Channel Adapter Registry — Maps every ChannelType to its Adapter class.
═══════════════════════════════════════════════════════════════════════
Import this module to get the ADAPTER_REGISTRY dict used by ChannelGateway.
"""

from typing import Dict, Type

from channels.base import ChannelAdapter, ChannelType

# ── Messaging (14) ──
from channels.adapters.messaging import (
    WhatsAppAdapter, TelegramAdapter, DiscordAdapter, SlackAdapter,
    SignalAdapter, MatrixAdapter, IRCAdapter, XMPPAdapter,
    WeChatAdapter, LINEAdapter, ViberAdapter,
    FacebookMessengerAdapter, InstagramDMAdapter, TwitterDMAdapter,
)

# ── Email (3) ──
from channels.adapters.email_adapters import (
    SMTPEmailAdapter, GmailAdapter, OutlookAdapter,
)

# ── Voice/Video (3) ──
from channels.adapters.voice import (
    WebRTCAdapter, TwilioVoiceAdapter, SIPAdapter,
)

# ── Web (4) ──
from channels.adapters.web import (
    RESTWebhookAdapter, WebSocketChannelAdapter, SSEAdapter, GraphQLAdapter,
)

# ── Developer (6) ──
from channels.adapters.developer import (
    GitHubAdapter, GitLabAdapter, JiraAdapter,
    LinearAdapter, NotionAdapter, ConfluenceAdapter,
)

# ── Business (6) ──
from channels.adapters.business import (
    SalesforceAdapter, HubSpotAdapter, ZendeskAdapter,
    IntercomAdapter, FreshdeskAdapter, ServiceNowAdapter,
)

# ── Collaboration (5) ──
from channels.adapters.collaboration import (
    MicrosoftTeamsAdapter, GoogleChatAdapter, ZoomChatAdapter,
    MattermostAdapter, RocketChatAdapter,
)

# ── IoT/Hardware (4) ──
from channels.adapters.iot import (
    MQTTAdapter, HTTPWebhookAdapter, GRPCAdapter, SerialAdapter,
)

# ── Custom/Infrastructure (7) ──
from channels.adapters.custom import (
    GenericWebhookAdapter, CLIPipeAdapter, UnixSocketAdapter,
    NamedPipeAdapter, RedisPubSubAdapter, KafkaAdapter, RabbitMQAdapter,
)


# ═══════════════════════════════════════════════════════════
# THE REGISTRY — 52 Adapters
# ═══════════════════════════════════════════════════════════

ADAPTER_REGISTRY: Dict[ChannelType, Type[ChannelAdapter]] = {
    # Messaging (14)
    ChannelType.WHATSAPP: WhatsAppAdapter,
    ChannelType.TELEGRAM: TelegramAdapter,
    ChannelType.DISCORD: DiscordAdapter,
    ChannelType.SLACK: SlackAdapter,
    ChannelType.SIGNAL: SignalAdapter,
    ChannelType.MATRIX: MatrixAdapter,
    ChannelType.IRC: IRCAdapter,
    ChannelType.XMPP: XMPPAdapter,
    ChannelType.WECHAT: WeChatAdapter,
    ChannelType.LINE: LINEAdapter,
    ChannelType.VIBER: ViberAdapter,
    ChannelType.FACEBOOK_MESSENGER: FacebookMessengerAdapter,
    ChannelType.INSTAGRAM_DM: InstagramDMAdapter,
    ChannelType.TWITTER_DM: TwitterDMAdapter,

    # Email (3)
    ChannelType.EMAIL_SMTP: SMTPEmailAdapter,
    ChannelType.EMAIL_GMAIL: GmailAdapter,
    ChannelType.EMAIL_OUTLOOK: OutlookAdapter,

    # Voice/Video (3)
    ChannelType.WEBRTC: WebRTCAdapter,
    ChannelType.TWILIO_VOICE: TwilioVoiceAdapter,
    ChannelType.SIP: SIPAdapter,

    # Web (4)
    ChannelType.REST_WEBHOOK: RESTWebhookAdapter,
    ChannelType.WEBSOCKET: WebSocketChannelAdapter,
    ChannelType.SSE: SSEAdapter,
    ChannelType.GRAPHQL: GraphQLAdapter,

    # Developer (6)
    ChannelType.GITHUB: GitHubAdapter,
    ChannelType.GITLAB: GitLabAdapter,
    ChannelType.JIRA: JiraAdapter,
    ChannelType.LINEAR: LinearAdapter,
    ChannelType.NOTION: NotionAdapter,
    ChannelType.CONFLUENCE: ConfluenceAdapter,

    # Business (6)
    ChannelType.SALESFORCE: SalesforceAdapter,
    ChannelType.HUBSPOT: HubSpotAdapter,
    ChannelType.ZENDESK: ZendeskAdapter,
    ChannelType.INTERCOM: IntercomAdapter,
    ChannelType.FRESHDESK: FreshdeskAdapter,
    ChannelType.SERVICENOW: ServiceNowAdapter,

    # Collaboration (5)
    ChannelType.MICROSOFT_TEAMS: MicrosoftTeamsAdapter,
    ChannelType.GOOGLE_CHAT: GoogleChatAdapter,
    ChannelType.ZOOM_CHAT: ZoomChatAdapter,
    ChannelType.MATTERMOST: MattermostAdapter,
    ChannelType.ROCKETCHAT: RocketChatAdapter,

    # IoT/Hardware (4)
    ChannelType.MQTT: MQTTAdapter,
    ChannelType.HTTP_WEBHOOK: HTTPWebhookAdapter,
    ChannelType.GRPC: GRPCAdapter,
    ChannelType.SERIAL: SerialAdapter,

    # Custom/Infrastructure (7)
    ChannelType.GENERIC_WEBHOOK: GenericWebhookAdapter,
    ChannelType.CLI_PIPE: CLIPipeAdapter,
    ChannelType.UNIX_SOCKET: UnixSocketAdapter,
    ChannelType.NAMED_PIPE: NamedPipeAdapter,
    ChannelType.REDIS_PUBSUB: RedisPubSubAdapter,
    ChannelType.KAFKA: KafkaAdapter,
    ChannelType.RABBITMQ: RabbitMQAdapter,
}

__all__ = ["ADAPTER_REGISTRY"]
