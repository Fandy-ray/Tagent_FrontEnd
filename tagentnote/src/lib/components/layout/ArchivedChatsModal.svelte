<script lang="ts">
	import ChatsModal, { type ChatRow } from './ChatsModal.svelte';

	type Props = {
		show?: boolean;
		chats: ChatRow[];
		onUpdate?: () => void;
		onDelete?: (id: string) => void;
	};

	let { show = $bindable(false), chats, onUpdate = () => {}, onDelete = () => {} }: Props = $props();

	const handleUnarchive = (id: string) => {
		chats = chats.map((c) => (c.id === id ? { ...c, archived: false } : c));
	};
</script>

<ChatsModal
	bind:show
	title="已归档的对话"
	emptyPlaceholder="暂无已归档的对话"
	chats={chats.filter((c) => c.archived)}
	{onUpdate}
	{onDelete}
	onUnarchive={handleUnarchive}
/>
