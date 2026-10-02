<script lang="ts">
	import ChatsModal, { type ChatRow } from './ChatsModal.svelte';

	type Props = {
		show?: boolean;
		chats: ChatRow[];
		onUpdate?: () => void;
		onDelete?: (id: string) => void;
		/** 取消归档：由宿主改它自己的对话列表。这里改 chats 只是改了一份副本，宿主看不见 */
		onUnarchive?: (id: string) => void;
		/** 点开一段归档的对话 */
		onOpenChat?: (id: string) => void;
	};

	let {
		show = $bindable(false),
		chats,
		onUpdate = () => {},
		onDelete = () => {},
		onUnarchive = () => {},
		onOpenChat
	}: Props = $props();
</script>

<ChatsModal
	bind:show
	title="已归档的对话"
	emptyPlaceholder="暂无已归档的对话"
	chats={chats.filter((c) => c.archived)}
	{onUpdate}
	{onDelete}
	{onUnarchive}
	onOpen={onOpenChat}
/>
