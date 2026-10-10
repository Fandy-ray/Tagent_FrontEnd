import { env as publicEnv } from '$env/dynamic/public';

export type AgentUserModelProvider = {
	id: string;
	name: string;
	base_url: string;
	upstream_model: string;
	auth_mode: 'bearer' | 'none';
	api_key_masked?: string;
	model_id?: string;
	temperature: number;
	enabled: boolean;
};

export type AgentUserModelProviderForm = {
	name: string;
	base_url: string;
	upstream_model: string;
	auth_mode: 'bearer' | 'none';
	api_key: string;
	temperature: number;
	enabled: boolean;
};

export type AgentUserModelProvidersResponse = {
	providers: AgentUserModelProvider[];
	default_model_id: string;
};

const baseUrl = () => (publicEnv.PUBLIC_BACKEND_URL ?? '') + '/api/v1/agents';

async function request<T>(
	token: string,
	url: string,
	method: 'GET' | 'POST' | 'PUT' | 'DELETE',
	body?: unknown
): Promise<T> {
	const headers: Record<string, string> = {
		'Content-Type': 'application/json',
		Authorization: `Bearer ${token}`
	};
	const res = await fetch(url, {
		method,
		headers,
		body: body ? JSON.stringify(body) : undefined
	});
	if (!res.ok) {
		let message = `${res.status} ${res.statusText}`;
		try {
			const data = await res.json();
			if (data?.detail) message = data.detail;
			else if (data?.message) message = data.message;
		} catch {
			// ignore parse errors
		}
		throw new Error(message);
	}
	if (res.status === 204) return undefined as T;
	return (await res.json()) as T;
}

export const getAgentUserModelProviders = async (
	token: string
): Promise<AgentUserModelProvidersResponse> => {
	return request<AgentUserModelProvidersResponse>(
		token,
		`${baseUrl()}/user-model-providers`,
		'GET'
	);
};

export const createAgentUserModelProvider = async (
	token: string,
	payload: AgentUserModelProviderForm
): Promise<AgentUserModelProvider> => {
	return request<AgentUserModelProvider>(
		token,
		`${baseUrl()}/user-model-providers`,
		'POST',
		payload
	);
};

export const updateAgentUserModelProvider = async (
	token: string,
	id: string,
	payload: Partial<AgentUserModelProviderForm>
): Promise<AgentUserModelProvider> => {
	return request<AgentUserModelProvider>(
		token,
		`${baseUrl()}/user-model-providers/${id}`,
		'PUT',
		payload
	);
};

export const deleteAgentUserModelProvider = async (token: string, id: string): Promise<void> => {
	return request<void>(token, `${baseUrl()}/user-model-providers/${id}`, 'DELETE');
};

export const setAgentUserDefaultModel = async (token: string, modelId: string): Promise<void> => {
	return request<void>(token, `${baseUrl()}/user-model-providers/default`, 'POST', {
		model_id: modelId
	});
};
