import { getContext, hasContext } from 'svelte';
import { get } from 'svelte/store';
import type { I18nStore } from './index';

export const i18n = {
	t: (key: string, params?: Record<string, string | number>): string => {
		if (!hasContext('i18n')) {
			return key;
		}
		const store = get(getContext<I18nStore>('i18n'));
		if (typeof store.t === 'function') {
			return store.t(key, params);
		}
		return key;
	}
};
