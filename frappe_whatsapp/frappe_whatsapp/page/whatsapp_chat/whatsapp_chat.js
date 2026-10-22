frappe.pages["whatsapp-chat"].on_page_load = function (wrapper) {
	wrapper.whatsapp_chat = new WhatsAppChatPage(wrapper);
};

frappe.pages["whatsapp-chat"].on_page_show = function (wrapper) {
	wrapper.whatsapp_chat && wrapper.whatsapp_chat.on_show();
};

frappe.pages["whatsapp-chat"].on_page_hide = function (wrapper) {
	wrapper.whatsapp_chat && wrapper.whatsapp_chat.on_hide();
};

const WA_METHOD = "frappe_whatsapp.frappe_whatsapp.page.whatsapp_chat.whatsapp_chat.";
const WA_POLL_MS = 20000;
const WA_SESSION_HOURS = 24;

const WA_EMOJI = [
	{
		key: "smileys",
		icon: "😀",
		label: "Smileys & People",
		emoji: "😀 😃 😄 😁 😆 😅 🤣 😂 🙂 🙃 😉 😊 😇 🥰 😍 🤩 😘 😗 😚 😙 😋 😛 😜 🤪 😝 🤑 🤗 🤭 🤫 🤔 🤐 🤨 😐 😑 😶 😏 😒 🙄 😬 😌 😔 😪 🤤 😴 😷 🤒 🤕 🤢 🤮 🥵 🥶 🥴 😵 🤯 🤠 🥳 😎 🤓 🧐 😕 😟 🙁 😮 😯 😲 😳 🥺 😦 😧 😨 😰 😥 😢 😭 😱 😖 😣 😞 😓 😩 😫 🥱 😤 😡 😠 🤬 😈 👿 💀 💩 🤡 👻 👽 🤖 😺 😸 😹 😻 😼 😽 🙀 😿 😾",
	},
	{
		key: "gestures",
		icon: "👍",
		label: "Gestures",
		emoji: "👋 🤚 🖐️ ✋ 🖖 👌 🤌 🤏 ✌️ 🤞 🤟 🤘 🤙 👈 👉 👆 🖕 👇 ☝️ 👍 👎 ✊ 👊 🤛 🤜 👏 🙌 👐 🤲 🤝 🙏 ✍️ 💅 🤳 💪 🦾 👀 👁️ 👅 👄 🧠 👶 🧒 👦 👧 🧑 👨 👩 🧓 👴 👵 🙋 🙆 🙅 🤷 🤦 🙇 💁 🧑‍💻 🧑‍💼 🧑‍🏫 🧑‍🍳 🧑‍🔧 👮 🕵️ 💂 👷 🤴 👸 👰 🤵 🎅 🏃 🚶 💃 🕺 👯 🧘 👪",
	},
	{
		key: "hearts",
		icon: "❤️",
		label: "Hearts",
		emoji: "❤️ 🧡 💛 💚 💙 💜 🖤 🤍 🤎 💔 ❣️ 💕 💞 💓 💗 💖 💘 💝 💟 ♥️ 💋 💌 💐 🌹 🥀 💯 💢 💥 💫 💦 💨 🕳️ 💬 🗨️ 💭 💤",
	},
	{
		key: "nature",
		icon: "🐶",
		label: "Animals & Nature",
		emoji: "🐶 🐱 🐭 🐹 🐰 🦊 🐻 🐼 🐨 🐯 🦁 🐮 🐷 🐸 🐵 🙈 🙉 🙊 🐔 🐧 🐦 🐤 🦆 🦅 🦉 🐺 🐗 🐴 🦄 🐝 🐛 🦋 🐌 🐞 🐢 🐍 🦎 🐙 🦑 🦀 🐠 🐟 🐬 🐳 🦈 🐊 🐅 🐆 🦓 🦍 🐘 🦛 🦏 🐪 🦒 🦘 🐃 🐄 🐎 🐑 🐐 🐕 🐈 🐓 🦚 🦜 🌵 🎄 🌲 🌳 🌴 🌱 🌿 ☘️ 🍀 🍁 🍂 🍃 🌺 🌻 🌼 🌷 🌸 🌍 🌙 ⭐ 🌟 ✨ ⚡ 🔥 🌈 ☀️ ⛅ ☁️ 🌧️ ⛈️ ❄️ ☃️ 💧 🌊",
	},
	{
		key: "food",
		icon: "🍔",
		label: "Food & Drink",
		emoji: "🍏 🍎 🍐 🍊 🍋 🍌 🍉 🍇 🍓 🫐 🍈 🍒 🍑 🥭 🍍 🥥 🥝 🍅 🥑 🍆 🥔 🥕 🌽 🌶️ 🥒 🥬 🥦 🧄 🧅 🍄 🥜 🍞 🥐 🥖 🥨 🥯 🥞 🧇 🧀 🍖 🍗 🥩 🥓 🍔 🍟 🍕 🌭 🥪 🌮 🌯 🥗 🍝 🍜 🍲 🍛 🍣 🍱 🥟 🍤 🍚 🍙 🍘 🍥 🥮 🍢 🍡 🍧 🍨 🍦 🥧 🧁 🍰 🎂 🍮 🍭 🍬 🍫 🍿 🍩 🍪 🥛 ☕ 🍵 🧃 🥤 🍶 🍺 🍻 🥂 🍷 🥃 🍸 🍹 🍾 🧊",
	},
	{
		key: "activities",
		icon: "⚽",
		label: "Activities",
		emoji: "⚽ 🏀 🏈 ⚾ 🎾 🏐 🏉 🥏 🎱 🏓 🏸 🏒 🏑 🏏 🥅 ⛳ 🏹 🎣 🥊 🥋 🎽 🛹 ⛸️ 🎿 🏋️ 🤸 ⛹️ 🤺 🏊 🚴 🏆 🥇 🥈 🥉 🏅 🎖️ 🎗️ 🎫 🎟️ 🎪 🎭 🎨 🎬 🎤 🎧 🎼 🎹 🥁 🎷 🎺 🎸 🎻 🎲 ♟️ 🎯 🎳 🎮 🧩 🎉 🎊 🎈 🎁 🎀 🪅",
	},
	{
		key: "travel",
		icon: "🚗",
		label: "Travel & Places",
		emoji: "🚗 🚕 🚙 🚌 🚎 🏎️ 🚓 🚑 🚒 🚐 🛻 🚚 🚛 🚜 🛵 🏍️ 🚲 🛴 🚨 🚔 🚍 🚘 🚖 🚡 🚠 🚟 🚃 🚋 🚝 🚄 🚅 🚈 🚂 🚆 🚇 ✈️ 🛫 🛬 🚁 🚀 🛸 ⛵ 🚤 🛳️ ⛴️ 🚢 ⚓ ⛽ 🚧 🚦 🗺️ 🗽 🗼 🏰 🏯 🏟️ 🎡 🎢 ⛲ ⛱️ 🏖️ 🏝️ 🏜️ 🌋 ⛰️ 🏔️ 🏕️ 🏠 🏡 🏢 🏬 🏣 🏥 🏦 🏨 🏪 🏫 🏛️ ⛪ 🕌 🕍 🌅 🌄 🌇 🌆 🌃",
	},
	{
		key: "objects",
		icon: "💡",
		label: "Objects",
		emoji: "⌚ 📱 💻 ⌨️ 🖥️ 🖨️ 🖱️ 💾 💿 📷 📸 📹 🎥 📞 ☎️ 📺 📻 ⏰ ⏳ 📡 🔋 🔌 💡 🔦 🕯️ 💸 💵 💴 💶 💷 💰 💳 💎 ⚖️ 🔧 🔨 🛠️ ⚙️ 🔩 🧱 🔫 💣 🔪 🛡️ 🔮 💊 💉 🩺 🧬 🦠 🧪 🌡️ 🧹 🧺 🧻 🚽 🛁 🔑 🗝️ 🚪 🛋️ 🛏️ 🧸 🖼️ 🛍️ 🛒 🎁 ✉️ 📩 📨 📧 📦 📮 📝 📁 📂 📅 📆 📇 📈 📉 📊 📋 📌 📍 📎 🖇️ 📏 📐 ✂️ 🗑️ 🔒 🔓 🔏 🔐 🔍 🔎 📚 📖 🔖 🏷️ ✏️ 🖊️ 🖋️ 🖌️ 🖍️",
	},
	{
		key: "symbols",
		icon: "✅",
		label: "Symbols",
		emoji: "✅ ☑️ ✔️ ❌ ❎ ➕ ➖ ➗ ✖️ ♾️ ‼️ ⁉️ ❓ ❔ ❕ ❗ 〰️ 💲 ©️ ®️ ™️ 🔟 💯 🔢 🔠 🔡 🔤 🆗 🆕 🆓 🆒 🆙 🆘 ⛔ 🚫 📵 🔞 ☢️ ☣️ ⬆️ ↗️ ➡️ ↘️ ⬇️ ↙️ ⬅️ ↖️ ↕️ ↔️ ↩️ ↪️ 🔄 🔃 🔀 🔁 🔂 ▶️ ⏸️ ⏹️ ⏺️ ⏭️ ⏮️ ⏩ ⏪ 🔼 🔽 ℹ️ 🔴 🟠 🟡 🟢 🔵 🟣 ⚫ ⚪ 🟤 🔺 🔻 🔸 🔹 🔶 🔷 🔳 🔲 ▪️ ▫️ ⭕ 🔔 🔕 📣 📢 ⚠️ 🚸 ♻️ 🔰 🌐 🏁 🚩 🎌 🏴 🏳️ 🇰🇪 🇺🇬 🇹🇿 🇷🇼 🇪🇹 🇳🇬 🇿🇦 🇬🇧 🇺🇸 🇮🇳 🇦🇪",
	},
];

class WhatsAppChatPage {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("WhatsApp Chat"),
			single_column: true,
		});
		this.conversations = [];
		this.active = null;
		this.messages = [];
		this.has_more = false;
		this.search = "";
		this.poll_timer = null;
		this.refresh_queued = null;
		this.on_list_update = (data) => {
			if (data && data.doctype === "WhatsApp Message") this.queue_refresh();
		};

		this.inject_styles();
		this.make_layout();
		this.bind_events();
		this.load_conversations();
	}

	on_show() {
		// The list view clears every `list_update` listener when it opens, so subscribe again.
		frappe.realtime.doctype_subscribe("WhatsApp Message");
		frappe.realtime.off("list_update", this.on_list_update);
		frappe.realtime.on("list_update", this.on_list_update);
		clearInterval(this.poll_timer);
		this.poll_timer = setInterval(() => this.refresh(), WA_POLL_MS);
		const number = frappe.utils.get_url_arg("number");
		if (number) this.open_conversation(number.replace(/^\+/, ""));
	}

	on_hide() {
		frappe.realtime.off("list_update", this.on_list_update);
		clearInterval(this.poll_timer);
	}

	inject_styles() {
		if (document.getElementById("wa-chat-styles")) return;
		const style = document.createElement("style");
		style.id = "wa-chat-styles";
		style.textContent = `
			.wa-app {
				--wa-green: #00a884;
				--wa-green-dark: #008069;
				--wa-panel: #ffffff;
				--wa-panel-soft: #f0f2f5;
				--wa-chat-bg: #efeae2;
				--wa-in: #ffffff;
				--wa-out: #d9fdd3;
				--wa-text: #111b21;
				--wa-muted: #667781;
				--wa-border: #e9edef;
				--wa-hover: #f5f6f6;
				--wa-active: #f0f2f5;
				--wa-tick-read: #53bdeb;
				--wa-danger: #ea0038;
				--wa-shadow: 0 1px 0.5px rgba(11, 20, 26, 0.13);
			}
			[data-theme="dark"] .wa-app {
				--wa-panel: #111b21;
				--wa-panel-soft: #202c33;
				--wa-chat-bg: #0b141a;
				--wa-in: #202c33;
				--wa-out: #005c4b;
				--wa-text: #e9edef;
				--wa-muted: #8696a0;
				--wa-border: #222d34;
				--wa-hover: #202c33;
				--wa-active: #2a3942;
			}
			.wa-app {
				display: flex;
				height: calc(100vh - var(--navbar-height, 48px) - 110px);
				min-height: 480px;
				border: 1px solid var(--wa-border);
				border-radius: 12px;
				overflow: hidden;
				background: var(--wa-panel);
				color: var(--wa-text);
			}
			.wa-sidebar {
				width: 340px;
				min-width: 280px;
				display: flex;
				flex-direction: column;
				border-right: 1px solid var(--wa-border);
				background: var(--wa-panel);
			}
			.wa-sidebar-head, .wa-chat-head {
				display: flex;
				align-items: center;
				gap: 10px;
				padding: 10px 16px;
				min-height: 60px;
				background: var(--wa-panel-soft);
			}
			.wa-sidebar-head h4 { margin: 0; flex: 1; font-size: 18px; font-weight: 600; color: var(--wa-text); }
			.wa-icon-btn {
				border: 0;
				background: transparent;
				color: var(--wa-muted);
				width: 36px;
				height: 36px;
				border-radius: 50%;
				display: inline-flex;
				align-items: center;
				justify-content: center;
				cursor: pointer;
			}
			.wa-icon-btn:hover { background: var(--wa-active); color: var(--wa-text); }
			.wa-search { padding: 8px 12px; border-bottom: 1px solid var(--wa-border); }
			.wa-search input {
				width: 100%;
				border: 0;
				border-radius: 8px;
				padding: 8px 12px;
				background: var(--wa-panel-soft);
				color: var(--wa-text);
				outline: none;
			}
			.wa-list { flex: 1; overflow-y: auto; }
			.wa-item {
				display: flex;
				align-items: center;
				gap: 12px;
				padding: 10px 14px;
				cursor: pointer;
				border-bottom: 1px solid var(--wa-border);
			}
			.wa-item:hover { background: var(--wa-hover); }
			.wa-item.active { background: var(--wa-active); }
			.wa-avatar {
				width: 46px;
				height: 46px;
				border-radius: 50%;
				flex-shrink: 0;
				display: flex;
				align-items: center;
				justify-content: center;
				color: #fff;
				font-weight: 600;
				font-size: 16px;
			}
			.wa-item-body { flex: 1; min-width: 0; }
			.wa-item-top, .wa-item-bottom { display: flex; align-items: center; gap: 8px; }
			.wa-item-name {
				flex: 1;
				font-size: 15px;
				color: var(--wa-text);
				white-space: nowrap;
				overflow: hidden;
				text-overflow: ellipsis;
			}
			.wa-item-time { font-size: 12px; color: var(--wa-muted); flex-shrink: 0; }
			.wa-item.unread .wa-item-time { color: var(--wa-green); }
			.wa-item-preview {
				flex: 1;
				font-size: 13px;
				color: var(--wa-muted);
				white-space: nowrap;
				overflow: hidden;
				text-overflow: ellipsis;
			}
			.wa-badge {
				background: var(--wa-green);
				color: #fff;
				border-radius: 10px;
				min-width: 20px;
				height: 20px;
				padding: 0 6px;
				font-size: 12px;
				display: inline-flex;
				align-items: center;
				justify-content: center;
				flex-shrink: 0;
			}
			.wa-chat { flex: 1; display: flex; flex-direction: column; min-width: 0; background: var(--wa-chat-bg); }
			.wa-chat-head { border-left: 1px solid var(--wa-border); }
			.wa-chat-title { flex: 1; min-width: 0; }
			.wa-chat-title .name { font-size: 16px; color: var(--wa-text); font-weight: 500; }
			.wa-chat-title .sub { font-size: 13px; color: var(--wa-muted); }
			.wa-messages { flex: 1; overflow-y: auto; padding: 16px 7%; display: flex; flex-direction: column; gap: 2px; }
			.wa-load-more { align-self: center; margin-bottom: 8px; }
			.wa-day {
				align-self: center;
				margin: 10px 0 6px;
				padding: 5px 12px;
				border-radius: 8px;
				font-size: 12px;
				background: var(--wa-panel);
				color: var(--wa-muted);
				box-shadow: var(--wa-shadow);
			}
			.wa-bubble {
				max-width: 65%;
				padding: 6px 8px 4px 9px;
				border-radius: 8px;
				font-size: 14px;
				line-height: 1.4;
				box-shadow: var(--wa-shadow);
				color: var(--wa-text);
				word-wrap: break-word;
				margin-top: 2px;
			}
			.wa-bubble.in { align-self: flex-start; background: var(--wa-in); border-top-left-radius: 0; }
			.wa-bubble.out { align-self: flex-end; background: var(--wa-out); border-top-right-radius: 0; }
			.wa-bubble.failed { outline: 1px solid var(--wa-danger); }
			.wa-bubble img, .wa-bubble video { max-width: 100%; max-height: 320px; border-radius: 6px; display: block; margin-bottom: 4px; }
			.wa-bubble audio { max-width: 260px; }
			.wa-doc {
				display: flex;
				align-items: center;
				gap: 8px;
				padding: 8px;
				border-radius: 6px;
				background: rgba(0, 0, 0, 0.05);
				color: var(--wa-text) !important;
				margin-bottom: 4px;
			}
			.wa-tag { font-size: 11px; color: var(--wa-muted); text-transform: uppercase; letter-spacing: 0.03em; }
			.wa-meta { float: right; margin: 6px 0 -4px 10px; font-size: 11px; color: var(--wa-muted); display: inline-flex; align-items: center; gap: 3px; }
			.wa-tick.read { color: var(--wa-tick-read); }
			.wa-tick.failed { color: var(--wa-danger); }
			.wa-notice {
				margin: 0 16px 8px;
				padding: 8px 12px;
				border-radius: 8px;
				font-size: 12.5px;
				background: #fff8c5;
				color: #5c4a00;
			}
			[data-theme="dark"] .wa-notice { background: #3b3416; color: #f1e3a3; }
			.wa-notice a { color: inherit; text-decoration: underline; }
			.wa-composer { display: flex; align-items: flex-end; gap: 8px; padding: 10px 16px; background: var(--wa-panel-soft); }
			.wa-composer textarea {
				flex: 1;
				resize: none;
				border: 0;
				border-radius: 8px;
				padding: 10px 12px;
				max-height: 140px;
				background: var(--wa-panel);
				color: var(--wa-text);
				outline: none;
				font-size: 14px;
			}
			.wa-emoji-panel {
				display: none;
				flex-direction: column;
				height: 280px;
				border-top: 1px solid var(--wa-border);
				background: var(--wa-panel-soft);
			}
			.wa-emoji-panel.open { display: flex; }
			.wa-emoji-tabs { display: flex; gap: 2px; padding: 6px 12px 0; border-bottom: 1px solid var(--wa-border); overflow-x: auto; }
			.wa-emoji-tab {
				border: 0;
				background: transparent;
				font-size: 20px;
				padding: 4px 8px 6px;
				cursor: pointer;
				border-bottom: 3px solid transparent;
				opacity: 0.6;
			}
			.wa-emoji-tab.active { border-bottom-color: var(--wa-green); opacity: 1; }
			.wa-emoji-grid {
				flex: 1;
				overflow-y: auto;
				padding: 8px 12px;
				display: grid;
				grid-template-columns: repeat(auto-fill, minmax(40px, 1fr));
				align-content: start;
			}
			.wa-emoji {
				border: 0;
				background: transparent;
				font-size: 26px;
				line-height: 1;
				height: 40px;
				border-radius: 8px;
				cursor: pointer;
			}
			.wa-emoji:hover { background: var(--wa-active); }
			.wa-emoji-empty { grid-column: 1 / -1; text-align: center; color: var(--wa-muted); font-size: 13px; padding: 24px; }
			.wa-emoji-btn.active { color: var(--wa-green); }
			.wa-bubble.jumbo .wa-text { font-size: 36px; line-height: 1.2; }
			.wa-send { background: var(--wa-green); color: #fff; }
			.wa-send:hover { background: var(--wa-green-dark); color: #fff; }
			.wa-empty {
				flex: 1;
				display: flex;
				flex-direction: column;
				align-items: center;
				justify-content: center;
				gap: 8px;
				color: var(--wa-muted);
				text-align: center;
				padding: 24px;
				background: var(--wa-panel-soft);
			}
			.wa-empty h3 { color: var(--wa-text); font-weight: 400; margin: 8px 0 0; }
			.wa-list-empty { padding: 24px; text-align: center; color: var(--wa-muted); font-size: 13px; }
			.wa-back { display: none; }
			@media (max-width: 768px) {
				.wa-app { height: calc(100vh - var(--navbar-height, 48px) - 90px); }
				.wa-sidebar { width: 100%; min-width: 0; border-right: 0; }
				.wa-app .wa-chat { display: none; }
				.wa-app.chat-open .wa-sidebar { display: none; }
				.wa-app.chat-open .wa-chat { display: flex; }
				.wa-back { display: inline-flex; }
				.wa-messages { padding: 12px; }
				.wa-bubble { max-width: 85%; }
			}
		`;
		document.head.appendChild(style);
	}

	make_layout() {
		this.$app = $(`
			<div class="wa-app">
				<div class="wa-sidebar">
					<div class="wa-sidebar-head">
						<h4>${__("Chats")}</h4>
						<button class="wa-icon-btn wa-new" title="${__("New chat")}">${frappe.utils.icon("square-pen", "md")}</button>
						<button class="wa-icon-btn wa-refresh" title="${__("Refresh")}">${frappe.utils.icon("refresh-cw", "md")}</button>
					</div>
					<div class="wa-search"><input type="search" placeholder="${__("Search name or number")}"></div>
					<div class="wa-list"></div>
				</div>
				<div class="wa-chat"></div>
			</div>
		`).appendTo(this.page.main);
		this.$list = this.$app.find(".wa-list");
		this.$chat = this.$app.find(".wa-chat");
		this.render_empty_chat();
	}

	bind_events() {
		this.$app.find(".wa-search input").on(
			"input",
			frappe.utils.debounce((e) => {
				this.search = e.target.value;
				this.load_conversations();
			}, 300)
		);
		this.$app.find(".wa-refresh").on("click", () => this.refresh());
		this.$app.find(".wa-new").on("click", () => this.new_chat());
		this.$list.on("click", ".wa-item", (e) => {
			this.open_conversation($(e.currentTarget).attr("data-number"));
		});
	}

	// Data

	load_conversations() {
		return frappe
			.xcall(WA_METHOD + "get_conversations", { search: this.search || null })
			.then((rows) => {
				this.conversations = rows || [];
				this.render_list();
			});
	}

	refresh() {
		this.load_conversations();
		if (this.active) this.load_messages({ keep_scroll: true });
	}

	queue_refresh() {
		clearTimeout(this.refresh_queued);
		this.refresh_queued = setTimeout(() => this.refresh(), 600);
	}

	open_conversation(number) {
		if (!number) return;
		this.active = String(number);
		this.messages = [];
		this.$app.addClass("chat-open");
		this.$list.find(".wa-item").removeClass("active");
		this.$list.find(`.wa-item[data-number="${CSS.escape(this.active)}"]`).addClass("active");
		this.render_chat_shell();
		this.load_messages().then(() => this.mark_read());
	}

	load_messages({ keep_scroll = false, before = null } = {}) {
		const number = this.active;
		return frappe
			.xcall(WA_METHOD + "get_messages", { number, before })
			.then((res) => {
				if (number !== this.active) return;
				this.profile = res.profile;
				this.has_more = res.has_more;
				if (before) {
					this.messages = res.messages.concat(this.messages);
				} else if (keep_scroll && this.messages.length > res.messages.length) {
					// Polling fetches the latest page only; keep older pages already loaded.
					const oldest = res.messages[0] && res.messages[0].creation;
					this.messages = this.messages.filter((m) => m.creation < oldest).concat(res.messages);
				} else {
					this.messages = res.messages;
				}
				this.render_header();
				this.render_messages({ keep_scroll, prepend: !!before });
				if (keep_scroll) this.mark_read();
			});
	}

	mark_read() {
		const conversation = this.conversations.find((c) => c.number === this.active);
		if (!conversation || !conversation.unread) return;
		conversation.unread = 0;
		this.render_list();
		frappe.xcall(WA_METHOD + "mark_as_read", { number: this.active });
	}

	send(message, attach) {
		if (!this.active) return;
		const number = this.active;
		this.$composer.find(".wa-send").prop("disabled", true);
		return frappe
			.xcall(WA_METHOD + "send_message", { number, message: message || null, attach: attach || null })
			.then((msg) => {
				if (number === this.active) {
					this.messages.push(msg);
					this.render_messages();
				}
				this.load_conversations();
			})
			.finally(() => this.$composer.find(".wa-send").prop("disabled", false));
	}

	new_chat() {
		frappe.prompt(
			[
				{
					fieldname: "number",
					fieldtype: "Data",
					label: __("WhatsApp number"),
					description: __("Include the country code, e.g. 254712345678"),
					reqd: 1,
				},
			],
			(values) => {
				const number = values.number.replace(/[^\d]/g, "");
				if (number.length < 8) {
					frappe.msgprint(__("Enter a valid number with country code"));
					return;
				}
				this.open_conversation(number);
			},
			__("New chat"),
			__("Open")
		);
	}

	// Rendering

	render_list() {
		if (!this.conversations.length) {
			this.$list.html(
				`<div class="wa-list-empty">${
					this.search ? __("No chats match your search") : __("No WhatsApp conversations yet")
				}</div>`
			);
			return;
		}
		this.$list.html(
			this.conversations
				.map((c) => {
					const unread = c.unread > 0;
					return `
						<div class="wa-item ${c.number === this.active ? "active" : ""} ${unread ? "unread" : ""}"
							data-number="${frappe.utils.escape_html(c.number)}">
							${this.avatar(c.title)}
							<div class="wa-item-body">
								<div class="wa-item-top">
									<span class="wa-item-name">${frappe.utils.escape_html(c.title)}</span>
									<span class="wa-item-time">${this.list_time(c.last_at)}</span>
								</div>
								<div class="wa-item-bottom">
									<span class="wa-item-preview">${c.type === "Outgoing" ? this.ticks(c.status) + " " : ""}${frappe.utils.escape_html(
										this.preview(c)
									)}</span>
									${unread ? `<span class="wa-badge">${c.unread}</span>` : ""}
								</div>
							</div>
						</div>`;
				})
				.join("")
		);
	}

	render_empty_chat() {
		this.$chat.html(`
			<div class="wa-empty">
				${frappe.utils.icon("message-circle", "xl")}
				<h3>${__("WhatsApp Chat")}</h3>
				<p>${__("Select a chat to read and reply to messages.")}</p>
			</div>
		`);
	}

	render_chat_shell() {
		this.$chat.html(`
			<div class="wa-chat-head">
				<button class="wa-icon-btn wa-back" title="${__("Back")}">${frappe.utils.icon("arrow-left", "md")}</button>
				<span class="wa-chat-avatar"></span>
				<div class="wa-chat-title"><div class="name"></div><div class="sub"></div></div>
				<button class="wa-icon-btn wa-open-profile" title="${__("Open profile")}">${frappe.utils.icon("user-round", "md")}</button>
				<button class="wa-icon-btn wa-chat-refresh" title="${__("Refresh")}">${frappe.utils.icon("refresh-cw", "md")}</button>
			</div>
			<div class="wa-messages"></div>
			<div class="wa-notice" style="display:none"></div>
			<div class="wa-emoji-panel"></div>
			<div class="wa-composer">
				<button class="wa-icon-btn wa-emoji-btn" title="${__("Emoji")}">${frappe.utils.icon("face-slightly-smiling", "md")}</button>
				<button class="wa-icon-btn wa-attach" title="${__("Attach")}">${frappe.utils.icon("paperclip", "md")}</button>
				<textarea rows="1" placeholder="${__("Type a message")}"></textarea>
				<button class="wa-icon-btn wa-send" title="${__("Send")}">${frappe.utils.icon("send-horizontal", "md")}</button>
			</div>
		`);
		this.$messages = this.$chat.find(".wa-messages");
		this.$composer = this.$chat.find(".wa-composer");
		const $input = this.$composer.find("textarea");

		const autosize = () => {
			$input[0].style.height = "auto";
			$input[0].style.height = Math.min($input[0].scrollHeight, 140) + "px";
		};
		const submit = () => {
			const text = $input.val();
			if (!text.trim()) return;
			$input.val("");
			autosize();
			this.send(text);
		};

		$input.on("input", autosize).on("keydown", (e) => {
			if (e.key === "Enter" && !e.shiftKey) {
				e.preventDefault();
				submit();
			}
		});
		this.$composer.find(".wa-send").on("click", submit);
		this.$composer.find(".wa-attach").on("click", () => this.attach());
		this.$emoji_panel = this.$chat.find(".wa-emoji-panel");
		this.$composer.find(".wa-emoji-btn").on("click", () => this.toggle_emoji_panel());
		$input.on("keydown", (e) => {
			if (e.key === "Escape") this.toggle_emoji_panel(false);
		});
		this.$chat.find(".wa-back").on("click", () => {
			this.$app.removeClass("chat-open");
		});
		this.$chat.find(".wa-chat-refresh").on("click", () => this.load_messages({ keep_scroll: true }));
		this.$chat.find(".wa-open-profile").on("click", () => this.open_profile());
		this.$messages.on("click", ".wa-load-more", () => {
			const oldest = this.messages[0];
			if (oldest) this.load_messages({ before: oldest.creation });
		});
		this.render_header();
		$input.trigger("focus");
	}

	render_header() {
		if (!this.$chat.find(".wa-chat-head").length) return;
		const conversation = this.conversations.find((c) => c.number === this.active);
		const title =
			(this.profile && this.profile.profile_name) ||
			(conversation && conversation.title) ||
			`+${this.active}`;
		this.$chat.find(".wa-chat-avatar").html(this.avatar(title));
		this.$chat.find(".wa-chat-title .name").text(title);
		this.$chat.find(".wa-chat-title .sub").text(`+${this.active}`);
		this.render_session_notice();
	}

	render_session_notice() {
		const $notice = this.$chat.find(".wa-notice");
		const last_in = [...this.messages].reverse().find((m) => m.type === "Incoming");
		const hours = last_in ? moment().diff(moment(last_in.creation), "hours", true) : Infinity;
		if (hours < WA_SESSION_HOURS) {
			$notice.hide();
			return;
		}
		$notice
			.html(
				`${__(
					"No reply from this contact in the last 24 hours. WhatsApp only delivers approved template messages until they message you again."
				)} <a href="#" class="wa-template">${__("Send a template")}</a>`
			)
			.show();
		$notice.find(".wa-template").on("click", (e) => {
			e.preventDefault();
			frappe.new_doc("WhatsApp Message", {
				type: "Outgoing",
				to: this.active,
				message_type: "Template",
				use_template: 1,
			});
		});
	}

	render_messages({ keep_scroll = false, prepend = false } = {}) {
		if (!this.$messages) return;
		const el = this.$messages[0];
		const at_bottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
		const previous_height = el.scrollHeight;

		let html = this.has_more
			? `<button class="btn btn-xs btn-default wa-load-more">${__("Load earlier messages")}</button>`
			: "";
		let last_day = null;
		for (const m of this.messages) {
			const day = moment(m.creation).format("YYYY-MM-DD");
			if (day !== last_day) {
				html += `<div class="wa-day">${this.day_label(m.creation)}</div>`;
				last_day = day;
			}
			html += this.bubble(m);
		}
		if (!this.messages.length) {
			html = `<div class="wa-day">${__("No messages yet. Say hello!")}</div>`;
		}
		this.$messages.html(html);

		if (prepend) {
			el.scrollTop = el.scrollHeight - previous_height;
		} else if (!keep_scroll || at_bottom) {
			el.scrollTop = el.scrollHeight;
		}
		this.render_session_notice();
	}

	bubble(m) {
		const out = m.type === "Outgoing";
		const failed = out && (m.status || "").toLowerCase() === "failed";
		const url = m.attach ? frappe.utils.escape_html(m.attach) : "";
		let media = "";
		switch (m.content_type) {
			case "image":
			case "sticker":
				media = url ? `<a href="${url}" target="_blank"><img src="${url}" loading="lazy"></a>` : "";
				break;
			case "video":
				media = url ? `<video src="${url}" controls preload="metadata"></video>` : "";
				break;
			case "audio":
				media = url ? `<audio src="${url}" controls preload="none"></audio>` : "";
				break;
			case "document":
				media = url
					? `<a class="wa-doc" href="${url}" target="_blank">${frappe.utils.icon(
							"file-text",
							"md"
					  )}<span>${frappe.utils.escape_html(decodeURIComponent(url.split("/").pop()))}</span></a>`
					: "";
				break;
		}

		let label = "";
		if (m.message_type === "Template" && m.template) {
			label = `<div class="wa-tag">${__("Template")}: ${frappe.utils.escape_html(m.template)}</div>`;
		} else if (["reaction", "button", "flow", "order", "location", "contacts", "interactive"].includes(m.content_type)) {
			label = `<div class="wa-tag">${frappe.utils.escape_html(m.content_type)}</div>`;
		}

		const jumbo = !media && !label && this.is_only_emoji(m.message);
		return `
			<div class="wa-bubble ${out ? "out" : "in"} ${failed ? "failed" : ""} ${jumbo ? "jumbo" : ""}" title="${frappe.utils.escape_html(
				frappe.datetime.str_to_user(m.creation)
			)}">
				${label}${media}<span class="wa-text">${this.format_text(m.message)}</span>
				<span class="wa-meta">${moment(m.creation).format("HH:mm")}${out ? this.ticks(m.status) : ""}</span>
			</div>`;
	}

	attach() {
		new frappe.ui.FileUploader({
			// Meta downloads the file from its URL, so it has to be public.
			make_attachments_public: true,
			allow_toggle_private: false,
			allow_multiple: false,
			on_success: (file) => {
				const caption = this.$composer.find("textarea").val();
				this.$composer.find("textarea").val("");
				this.send(caption, file.file_url);
			},
		});
	}

	toggle_emoji_panel(open) {
		open = open === undefined ? !this.$emoji_panel.hasClass("open") : open;
		this.$emoji_panel.toggleClass("open", open);
		this.$composer.find(".wa-emoji-btn").toggleClass("active", open);
		if (open && !this.$emoji_panel.children().length) this.render_emoji_panel();
		if (open) this.show_emoji_group(this.recent_emoji().length ? "recent" : WA_EMOJI[0].key);
		this.$composer.find("textarea").trigger("focus");
	}

	render_emoji_panel() {
		const groups = [{ key: "recent", icon: "🕘", label: __("Recent") }, ...WA_EMOJI];
		this.$emoji_panel.html(`
			<div class="wa-emoji-tabs">
				${groups
					.map(
						(g) =>
							`<button class="wa-emoji-tab" data-group="${g.key}" title="${__(g.label)}">${g.icon}</button>`
					)
					.join("")}
			</div>
			<div class="wa-emoji-grid"></div>
		`);
		this.$emoji_panel.on("click", ".wa-emoji-tab", (e) => {
			this.show_emoji_group($(e.currentTarget).attr("data-group"));
		});
		// mousedown keeps the textarea's caret where it is.
		this.$emoji_panel.on("mousedown", ".wa-emoji", (e) => {
			e.preventDefault();
			this.insert_emoji($(e.currentTarget).text());
		});
	}

	show_emoji_group(key) {
		this.$emoji_panel.find(".wa-emoji-tab").removeClass("active");
		this.$emoji_panel.find(`.wa-emoji-tab[data-group="${key}"]`).addClass("active");
		const emoji = key === "recent" ? this.recent_emoji() : WA_EMOJI.find((g) => g.key === key).emoji.split(" ");
		this.$emoji_panel
			.find(".wa-emoji-grid")
			.html(
				emoji.length
					? emoji.map((e) => `<button class="wa-emoji">${e}</button>`).join("")
					: `<div class="wa-emoji-empty">${__("Emoji you use will show up here")}</div>`
			)
			.scrollTop(0);
	}

	insert_emoji(emoji) {
		const input = this.$composer.find("textarea")[0];
		const start = input.selectionStart ?? input.value.length;
		const end = input.selectionEnd ?? input.value.length;
		input.value = input.value.slice(0, start) + emoji + input.value.slice(end);
		input.selectionStart = input.selectionEnd = start + emoji.length;
		$(input).trigger("input").trigger("focus");

		const recent = [emoji, ...this.recent_emoji().filter((e) => e !== emoji)].slice(0, 32);
		try {
			localStorage.setItem("wa_chat_recent_emoji", JSON.stringify(recent));
		} catch (e) {
			// Recents are a convenience; ignore storage being unavailable.
		}
	}

	recent_emoji() {
		try {
			return JSON.parse(localStorage.getItem("wa_chat_recent_emoji")) || [];
		} catch (e) {
			return [];
		}
	}

	is_only_emoji(text) {
		if (!text) return false;
		const trimmed = text.replace(/\s/g, "");
		if (!trimmed || !/^(\p{Extended_Pictographic}|\p{Emoji_Component}|‍|️)+$/u.test(trimmed)) return false;
		const count = [...new Intl.Segmenter().segment(trimmed)].length;
		return !/^[\d#*]+$/.test(trimmed) && count <= 3;
	}

	open_profile() {
		if (this.profile && this.profile.contact) {
			frappe.set_route("Form", "Contact", this.profile.contact);
		} else if (this.profile) {
			frappe.set_route("Form", "WhatsApp Profiles", this.profile.name);
		} else {
			frappe.new_doc("WhatsApp Profiles", { number: this.active });
		}
	}

	// Helpers

	avatar(title) {
		const colors = ["#00a884", "#53bdeb", "#7f66ff", "#fa6533", "#25d366", "#e542a3", "#ffbc38", "#02a698"];
		const text = String(title || "?").replace(/^\+/, "");
		let hash = 0;
		for (const ch of text) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
		const initials = /^\d/.test(text)
			? frappe.utils.icon("user-round", "md")
			: frappe.utils.escape_html(frappe.get_abbr(text, 2));
		return `<div class="wa-avatar" style="background:${colors[hash % colors.length]}">${initials}</div>`;
	}

	ticks(status) {
		const s = (status || "").toLowerCase();
		if (s === "failed") return `<span class="wa-tick failed">${frappe.utils.icon("circle-alert", "xs")}</span>`;
		if (s === "read") return `<span class="wa-tick read">${frappe.utils.icon("check-check", "xs")}</span>`;
		if (s === "delivered") return `<span class="wa-tick">${frappe.utils.icon("check-check", "xs")}</span>`;
		if (s === "sent") return `<span class="wa-tick">${frappe.utils.icon("check", "xs")}</span>`;
		return `<span class="wa-tick">${frappe.utils.icon("clock", "xs")}</span>`;
	}

	preview(c) {
		const text = $("<div>")
			.html(c.message || "")
			.text()
			.trim();
		if (text) return text;
		const labels = {
			image: __("Photo"),
			video: __("Video"),
			audio: __("Voice message"),
			document: __("Document"),
			sticker: __("Sticker"),
			location: __("Location"),
		};
		return labels[c.content_type] || c.content_type || "";
	}

	format_text(text) {
		if (!text) return "";
		// Outgoing messages may be stored as HTML from the form editor; show them as plain text.
		const plain = /<\w+[^>]*>/.test(text) ? $("<div>").html(text).text() : text;
		return frappe.utils
			.escape_html(plain)
			.replace(/\*([^*\n]+)\*/g, "<strong>$1</strong>")
			.replace(/(^|\s)_([^_\n]+)_/g, "$1<em>$2</em>")
			.replace(/~([^~\n]+)~/g, "<s>$1</s>")
			.replace(/```([^`]+)```/g, "<code>$1</code>")
			.replace(/\n/g, "<br>");
	}

	list_time(datetime) {
		const m = moment(datetime);
		if (m.isSame(moment(), "day")) return m.format("HH:mm");
		if (m.isSame(moment().subtract(1, "day"), "day")) return __("Yesterday");
		if (m.isAfter(moment().subtract(6, "days"))) return m.format("dddd");
		return frappe.datetime.str_to_user(datetime).split(" ")[0];
	}

	day_label(datetime) {
		const m = moment(datetime);
		if (m.isSame(moment(), "day")) return __("Today");
		if (m.isSame(moment().subtract(1, "day"), "day")) return __("Yesterday");
		return m.format("D MMMM YYYY");
	}
}
