import { browser } from '$app/environment';

import { defaultUserSettings, loadUserSettings } from './userSettings';

/**
 * 「这台设备是谁」：平台没有登录，后端的学习记录库靠这个匿名编号把同一个学生的
 * 答疑、批改、整卷记录串起来，昵称取设置里的「显示名称」。
 *
 * 它只是设备标记，不是身份认证：换浏览器、清缓存就是一个新编号。
 * 后端对应的校验在 basic-agent/app/api/learner.py，两边的格式要一致。
 */
const CLIENT_ID_KEY = 'tagentnote.client.id.v1';
const CLIENT_ID_PATTERN = /^[A-Za-z0-9_-]{8,64}$/;
const MAX_NAME_CHARS = 40;

// localStorage 用不了（无痕模式、被禁用）时，至少在这次打开页面期间保持同一个编号
let fallbackId: string | null = null;

const newClientId = () => {
	if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
		return crypto.randomUUID();
	}
	return `dev_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 12)}`;
};

export function clientId(): string | null {
	if (!browser) return null;
	try {
		const saved = localStorage.getItem(CLIENT_ID_KEY);
		if (saved && CLIENT_ID_PATTERN.test(saved)) return saved;
		const created = newClientId();
		localStorage.setItem(CLIENT_ID_KEY, created);
		return created;
	} catch {
		fallbackId ??= newClientId();
		return fallbackId;
	}
}

// 临时对话期间不让后端留记录（界面答应过「消息不会被保存」）。答疑页进出临时对话时设置，离开答疑页时清掉
let recordingPaused = false;

export function setRecordingPaused(paused: boolean) {
	recordingPaused = paused;
}

/**
 * 发给 basic-agent 的身份头。昵称要 URL 编码：HTTP 头里放不了中文。
 *
 * 绝不抛异常：这只是附带的身份信息，存坏了的设置（昵称不是字符串之类）最多让这次请求不带昵称，
 * 不能让所有请求都在发出去之前就失败。
 */
export function learnerHeaders(): Record<string, string> {
	const headers: Record<string, string> = recordingPaused ? { 'X-Tagent-No-Record': '1' } : {};
	try {
		const id = clientId();
		if (!id) return headers;
		headers['X-Tagent-Client-Id'] = id;
		const raw = loadUserSettings().displayName;
		const name = typeof raw === 'string' ? raw.trim().slice(0, MAX_NAME_CHARS) : '';
		// 没改过的默认名（「Tagent」）不算昵称，免得全班都叫这个
		if (name && name !== defaultUserSettings().displayName) {
			headers['X-Tagent-Client-Name'] = encodeURIComponent(name);
		}
	} catch {
		// 见上：身份信息不全也照常发请求
	}
	return headers;
}
