<script lang="ts">
	type Props = {
		state?: boolean;
		id?: string;
		ariaLabelledbyId?: string;
		onChange?: (state: boolean) => void;
	};
	let { state = $bindable(true), id = '', ariaLabelledbyId = '', onChange = () => {} }: Props = $props();
</script>

<button
	type="button"
	role="switch"
	{id}
	aria-labelledby={ariaLabelledbyId || undefined}
	aria-checked={state}
	class="flex h-[1.125rem] min-h-[1.125rem] w-8 shrink-0 cursor-pointer items-center rounded-full px-1 mx-[1px] transition outline outline-1 outline-gray-800 {state
		? 'bg-emerald-700'
		: 'bg-transparent'}"
	onclick={() => {
		state = !state;
		onChange(state);
	}}
>
	<span
		class="pointer-events-none block size-3 shrink-0 rounded-full bg-white transition-transform {state
			? 'translate-x-3'
			: 'translate-x-0 shadow'}"
	></span>
</button>
