<script lang="ts">
	import ChatsModal, { type ChatRow } from './ChatsModal.svelte';

	type Props = {
		show?: boolean;
		chats: ChatRow[];
		onUpdate?: () => void;
		onDelete?: (id: string) => void;
	};

	let {
		show = $bindable(false),
		chats,
		onUpdate = () => {},
		onDelete = () => {}
	}: Props = $props();

	const handleUnshare = (id: string) => {
		chats = chats.map((c) => (c.id === id ? { ...c, shared: false, shareId: undefined } : c));
	};
</script>

<ChatsModal
	bind:show
	title="已分享的对话"
	emptyPlaceholder="暂无已分享的对话"
	shareUrl
	chats={chats.filter((c) => c.shared && c.shareId)}
	{onUpdate}
	{onDelete}
	onUnshare={handleUnshare}
/>
