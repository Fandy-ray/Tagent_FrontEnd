<script lang="ts">
	import MockMessageInput from './MockMessageInput.svelte';
	import MockSuggestions from './MockSuggestions.svelte';

	type Props = {
		modelName?: string;
		prompt?: string;
		generating?: boolean;
		onSubmit?: (content: string) => void;
		onStop?: () => void;
	};

	let {
		modelName = '',
		prompt = $bindable(''),
		generating = false,
		onSubmit = () => {},
		onStop = () => {}
	}: Props = $props();

	const selectSuggestion = (content: string) => {
		prompt = content;
		onSubmit(content);
	};
</script>

<div class="m-auto w-full max-w-6xl translate-y-6 px-2 py-24 text-center min-[640px]:px-20">
	<div class="flex w-full items-center gap-4 text-center text-3xl text-gray-100">
		<div class="flex w-full flex-col items-center justify-center">
			<div class="flex w-fit flex-row justify-center gap-3 px-5">
				<div class="flex shrink-0 justify-center">
					<div class="flex -space-x-4">
						<div
							class="flex size-10 items-center justify-center rounded-full bg-white text-[11px] font-black text-black"
							aria-hidden="true"
						>
							OI
						</div>
					</div>
				</div>

				<div class="flex items-center text-3xl">
					<span class="line-clamp-1">
						{modelName}
					</span>
				</div>
			</div>

			<div class="mt-1 mb-2 flex min-h-3"></div>

			<div class="w-full py-3 text-base font-normal md:max-w-3xl">
				<MockMessageInput
					bind:prompt
					placeholder="有什么我能帮您的吗？"
					{generating}
					{onSubmit}
					{onStop}
				/>
			</div>
		</div>
	</div>

	<div class="mx-auto mt-2 max-w-2xl">
		<div class="mx-5">
			<MockSuggestions inputValue={prompt} onSelect={selectSuggestion} />
		</div>
	</div>
</div>
