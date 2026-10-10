// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
declare global {
	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		// interface PageState {}
		// interface Platform {}
	}
}

export {};

declare module '$app/paths' {
	/** Runtime-built internal paths are validated by the caller's route construction. */
	export function resolve(path: string): string;
}
