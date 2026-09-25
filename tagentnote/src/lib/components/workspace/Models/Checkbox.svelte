<script lang="ts">
	type Props = {
		state?: 'checked' | 'unchecked';
		disabled?: boolean;
		onChange?: (state: 'checked' | 'unchecked') => void;
	};

	let { state = 'unchecked', disabled = false, onChange = () => {} }: Props = $props();
</script>

<button
	class="relative inline-block h-3.5 w-3.5 rounded-sm text-white outline -outline-offset-1 outline-[1.5px] outline-gray-600 transition-all {state !==
	'unchecked'
		? 'bg-white outline-white text-black'
		: 'hover:bg-gray-800 hover:outline-gray-500'} {disabled ? 'cursor-not-allowed opacity-50' : ''}"
	type="button"
	{disabled}
	aria-checked={state === 'checked'}
	role="checkbox"
	onclick={() => {
		if (disabled) return;
		const next = state === 'checked' ? 'unchecked' : 'checked';
		onChange(next);
	}}
>
	{#if state === 'checked'}
		<svg class="absolute inset-0 m-auto size-3.5" aria-hidden="true" fill="none" viewBox="0 0 24 24">
			<path
				stroke="currentColor"
				stroke-linecap="round"
				stroke-linejoin="round"
				stroke-width="3"
				d="m5 12 4.7 4.5 9.3-9"
			/>
		</svg>
	{/if}
</button>
