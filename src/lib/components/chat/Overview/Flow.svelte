<script lang="ts">
	import {
		Background,
		BackgroundVariant,
		ControlButton,
		Controls,
		SvelteFlow,
		type Edge,
		type Node
	} from '@xyflow/svelte';
	import '@xyflow/svelte/dist/style.css';

	import OverviewNode from './Node.svelte';

	type Props = {
		nodes?: Node[];
		edges?: Edge[];
		onNodeClick?: (messageId: string) => void;
		onToggleLayout?: (direction: 'vertical' | 'horizontal') => void;
	};

	let {
		nodes = $bindable([]),
		edges = $bindable([]),
		onNodeClick = () => {},
		onToggleLayout = () => {}
	}: Props = $props();

	const nodeTypes = {
		custom: OverviewNode
	};
</script>

<div class="h-full w-full">
	<SvelteFlow
		bind:nodes
		bind:edges
		{nodeTypes}
		fitView
		minZoom={0.2}
		maxZoom={1.5}
		colorMode="dark"
		nodesConnectable={false}
		nodesDraggable={false}
		elementsSelectable={true}
		panOnScroll
		onnodeclick={(event) => {
			const messageId = event.node.id;
			if (messageId) onNodeClick(messageId);
		}}
		class="overview-flow bg-[#212121]"
	>
		<Controls showLock={false} position="bottom-left">
			<ControlButton
				onclick={() => onToggleLayout('vertical')}
				title="纵向布局"
				aria-label="纵向布局"
			>
				<svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
					<path stroke-linecap="round" d="M4 6h16M4 12h10M4 18h16"></path>
				</svg>
			</ControlButton>
			<ControlButton
				onclick={() => onToggleLayout('horizontal')}
				title="横向布局"
				aria-label="横向布局"
			>
				<svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
					<path stroke-linecap="round" d="M6 4v16M12 4v10M18 4v16"></path>
				</svg>
			</ControlButton>
		</Controls>
		<Background variant={BackgroundVariant.Dots} gap={18} size={1} patternColor="#3f3f46" />
	</SvelteFlow>
</div>

<style>
	:global(.overview-flow .svelte-flow__attribution) {
		display: none;
	}
</style>
