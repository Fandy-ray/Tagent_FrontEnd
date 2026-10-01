export type ToastKind = 'info' | 'success' | 'error';

type ToastListener = (message: string, kind: ToastKind, ms: number) => void;

const listeners = new Set<ToastListener>();

export const onToast = (listener: ToastListener): (() => void) => {
	listeners.add(listener);
	return () => {
		listeners.delete(listener);
	};
};

const emit = (message: string, kind: ToastKind = 'info', ms = 2800) => {
	for (const listener of listeners) listener(message, kind, ms);
};

export const toast = {
	info: (message: string, ms?: number) => emit(message, 'info', ms),
	success: (message: string, ms?: number) => emit(message, 'success', ms),
	error: (message: string, ms?: number) => emit(message, 'error', ms)
};
