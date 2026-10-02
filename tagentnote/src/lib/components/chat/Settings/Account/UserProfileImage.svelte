<script lang="ts">
	type Props = {
		profileImageUrl: string;
		userName?: string;
		imageClassName?: string;
	};

	// 轻量 toast（无第三方依赖）
	const notify = (message: string, _kind: 'success' | 'error' | 'info' = 'info') => {
		console.log(`[toast][${_kind}] ${message}`);
		try {
			window.dispatchEvent(
				new CustomEvent('tagent-toast', { detail: { message, kind: _kind } })
			);
		} catch {
			// ignore
		}
	};
	// 下面调用的是 toast.success / toast.error / toast.info：只有一个函数的话，运行时会报
	// 「toast.success is not a function」（比如保存账号信息后对话框关不上）
	const toast = {
		info: (message: string) => notify(message, 'info'),
		success: (message: string) => notify(message, 'success'),
		error: (message: string) => notify(message, 'error')
	};

	let {
		profileImageUrl = $bindable(''),
		userName = '',
		imageClassName = 'size-14 md:size-18'
	}: Props = $props();

	let profileImageInputElement: HTMLInputElement | null = $state(null);

	const initialsFor = (name: string): string => {
		const trimmed = (name || '').trim();
		if (!trimmed) return 'U';
		return trimmed.slice(0, 1).toUpperCase();
	};

	const onFileChange = (event: Event) => {
		const target = event.target as HTMLInputElement;
		const files = target.files;
		if (!files || files.length === 0) return;
		const file = files[0];
		if (!['image/gif', 'image/webp', 'image/jpeg', 'image/png'].includes(file.type)) {
			toast.error('仅支持 PNG / JPEG / GIF / WebP');
			return;
		}
		const reader = new FileReader();
		reader.onload = (e) => {
			const originalImageUrl = `${e.target?.result ?? ''}`;
			const img = new Image();
			img.src = originalImageUrl;
			img.onload = () => {
				const canvas = document.createElement('canvas');
				const ctx = canvas.getContext('2d');
				if (!ctx) return;
				const aspectRatio = img.width / img.height;
				let newWidth: number;
				let newHeight: number;
				if (aspectRatio > 1) {
					newWidth = 250 * aspectRatio;
					newHeight = 250;
				} else {
					newWidth = 250;
					newHeight = 250 / aspectRatio;
				}
				canvas.width = 250;
				canvas.height = 250;
				const offsetX = (250 - newWidth) / 2;
				const offsetY = (250 - newHeight) / 2;
				ctx.drawImage(img, offsetX, offsetY, newWidth, newHeight);
				profileImageUrl = canvas.toDataURL('image/webp', 0.8);
				if (profileImageInputElement) profileImageInputElement.value = '';
			};
		};
		reader.readAsDataURL(file);
	};

	const removeImage = () => {
		profileImageUrl = '';
	};

	const useInitials = () => {
		profileImageUrl = '';
	};

</script>

<input
	id="profile-image-input"
	bind:this={profileImageInputElement}
	type="file"
	hidden
	accept="image/*"
	onchange={onFileChange}
/>

<div class="group flex flex-col self-start">
	<div class="flex self-center">
		<button
			type="button"
			class="relative rounded-full bg-gray-700"
			onclick={() => profileImageInputElement?.click()}
		>
			{#if profileImageUrl}
				<img
					src={profileImageUrl}
					alt="profile"
					class="rounded-full object-cover {imageClassName}"
				/>
			{:else}
				<div
					class="flex items-center justify-center rounded-full bg-amber-500 font-semibold text-white {imageClassName}"
				>
					<span class="text-lg md:text-xl">{initialsFor(userName)}</span>
				</div>
			{/if}

			<div class="absolute right-0 bottom-0 opacity-0 transition group-hover:opacity-100">
				<div class="rounded-full border-gray-100 bg-white p-1 text-black shadow">
					<svg
						xmlns="http://www.w3.org/2000/svg"
						viewBox="0 0 20 20"
						fill="currentColor"
						class="size-3"
					>
						<path
							d="m2.695 14.762-1.262 3.155a.5.5 0 0 0 .65.65l3.155-1.262a4 4 0 0 0 1.343-.886L17.5 5.501a2.121 2.121 0 0 0-3-3L3.58 13.419a4 4 0 0 0-.885 1.343Z"
						/>
					</svg>
				</div>
			</div>
		</button>
	</div>
	<div class="mt-2 flex w-full flex-col items-center justify-center">
		<button
			type="button"
			class="rounded-lg py-0.5 text-center text-xs text-gray-500 opacity-0 transition-all group-hover:opacity-100"
			onclick={removeImage}
		>
			移除
		</button>

		<button
			type="button"
			class="rounded-lg py-0.5 text-center text-xs text-gray-400 opacity-0 transition-all group-hover:opacity-100"
			onclick={useInitials}
		>
			首字母
		</button>

	</div>
</div>
