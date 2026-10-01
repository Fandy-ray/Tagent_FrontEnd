import { getContext, hasContext } from 'svelte';
import type { I18nStore } from './index';

export const i18n = {
	t: (key: string, params?: Record<string, string | number>): string => {
		if (!hasContext('i18n')) {
			return key;
		}
		const store = getContext<I18nStore>('i18n');
		const i18nInstance = store as any;
		if (typeof i18nInstance.t === 'function') {
			return i18nInstance.t(key, params);
		}
		return key;
	}
};
