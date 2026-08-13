// ── Types（对齐 basic-agent 响应结构）──

export type AgentModel = {
	id: string;
	name: string;
	object: 'model';
	created: number;
	owned_by: string;
};

export type AgentModelList = {
	object: 'list';
	data: AgentModel[];
};

export type AgentRagResponse = {
	code: number;
	msg: string;
	data: {
		user_question: string;
		final_answer: string;
		retrieved_context?: string;
		step_log?: string[];
	};
	model: string;
};

// ── Mock 知识库（模拟 RAG 检索结果）──

type KnowledgeEntry = {
	context: string;
	answer: string;
	sources: { title: string; page: string }[];
};

const KNOWLEDGE: Record<string, KnowledgeEntry> = {
	连续系统仿真: {
		context:
			'教材第3章 P42-P58：连续系统仿真是指对系统状态随时间连续变化的系统进行的仿真。系统状态变量是时间的连续函数，通常用微分方程描述。常见数值积分方法包括欧拉法、Runge-Kutta法、Adams法。核心要点：数值积分方法的选择与步长控制。',
		answer:
			'**连续系统仿真**是指对系统状态随时间连续变化的系统进行的仿真。\n\n### 主要特点\n1. 系统状态变量是时间的连续函数\n2. 通常用**微分方程**或**差分方程**描述\n3. 求解方法：欧拉法、**Runge-Kutta 法**、Adams 法、Gear 法\n\n### 关键概念\n- **步长控制**：步长过大会导致精度下降甚至不稳定，步长过小则计算量过大\n- **刚性系统**：特征值差异大的系统，需使用刚性求解器（如 Gear 法）\n\n### 典型应用\n电路仿真（SPICE）、机械运动仿真、过程控制系统。',
		sources: [
			{ title: '教材第3章 · 连续系统建模', page: 'P42-P58' },
			{ title: '讲义 · 数值积分方法', page: '第12讲' }
		]
	},
	离散事件: {
		context:
			'教材第5章 P89-P112：离散事件系统是一类仅在离散时间点上发生状态改变的系统。基本要素包括实体、事件、活动、属性、队列、时钟。主要仿真策略有事件调度法、活动扫描法、进程交互法。',
		answer:
			'**离散事件系统**是一类仅在离散时间点上发生状态改变的系统。\n\n### 六大基本要素\n1. **实体（Entity）**：系统中流动的对象，如顾客、工件、数据包\n2. **事件（Event）**：导致系统状态改变的瞬间发生的事\n3. **活动（Activity）**：两个事件之间的持续过程\n4. **属性（Attribute）**：实体的特征描述\n5. **队列（Queue）**：实体等待服务的位置\n6. **时钟（Clock）**：记录仿真时间的变量\n\n### 三种仿真策略\n| 策略 | 核心思想 | 适用场景 |\n|------|---------|--------|\n| 事件调度法 | 按事件发生时间推进 | 排队系统 |\n| 活动扫描法 | 扫描所有活动条件 | 制造系统 |\n| 进程交互法 | 以实体生命周期为主线 | 复杂系统 |',
		sources: [
			{ title: '教材第5章 · 离散事件系统仿真', page: 'P89-P112' },
			{ title: '实验指导 · 排队系统仿真', page: '实验3' }
		]
	},
	'验证与确认': {
		context:
			'教材第2章 P28-P35：验证（Verification）关注"模型建对了吗？"，确认（Validation）关注"建的是对的模型吗？"。验证检查概念模型到计算机模型的转换正确性；确认检查模型与真实系统的一致性。',
		answer:
			'**验证（Verification）**和**确认（Validation）**是仿真建模中两个不同但紧密相关的环节。\n\n### 对比表\n| 维度 | 验证（Verification） | 确认（Validation） |\n|------|---------------------|-------------------|\n| 关注问题 | "模型建对了吗？" | "建的是对的模型吗？" |\n| 对象 | 概念模型 → 计算机模型 | 真实系统 → 概念模型 |\n| 方法 | 代码审查、单元测试、跟踪调试 | 灵敏度分析、极端条件测试、统计比较 |\n| 时机 | 建模过程中持续进行 | 模型完成后、应用前 |\n\n### 记忆口诀\n> **验证是检查"做事正确"，确认是检查"做正确的事"。**\n\n### 常用方法\n- **验证**：静态代码分析、断点调试、子模型测试、动画可视化\n- **确认**：Turing 测试、灵敏度分析、历史数据对比、统计假设检验',
		sources: [
			{ title: '教材第2章 · 仿真建模方法论', page: 'P28-P35' },
			{ title: '论文参考 · V&V 技术综述', page: '-' }
		]
	},
	状态空间: {
		context:
			'教材第4章 P65-P78：状态空间模型是现代控制理论与系统仿真的基础框架。状态变量是一组能够完全描述系统动态行为的最小变量集合。状态方程 ẋ=Ax+Bu 描述状态如何随时间变化，输出方程 y=Cx+Du 描述如何从状态得到输出。',
		answer:
			'**状态空间模型**是现代控制理论与系统仿真的基础框架。\n\n### 核心概念\n- **状态变量**：一组能够完全描述系统动态行为的**最小变量集合**\n- **状态方程**：ẋ = Ax + Bu（描述状态随时间变化）\n- **输出方程**：y = Cx + Du（描述状态到输出的映射）\n\n### 在仿真中的优势\n1. 统一处理 SISO 和 MIMO 系统\n2. 便于计算机数值求解（矩阵运算）\n3. 能描述系统**内部状态**，而不仅仅是输入输出关系\n4. 可直接分析能控性、能观性\n\n### 典型例题\n将传递函数 `G(s) = (s+2)/(s²+3s+2)` 转换为状态空间可控标准型表示。',
		sources: [
			{ title: '教材第4章 · 状态空间建模', page: 'P65-P78' },
			{ title: '习题解答 · 第4章', page: '题4.3-4.7' }
		]
	}
};

const DEFAULT_KNOWLEDGE: KnowledgeEntry = {
	context: '教材全书：系统建模与仿真课程内容涵盖建模方法论、连续系统仿真、离散事件系统仿真、仿真模型验证与确认、仿真实验设计与结果分析等。',
	answer:
		'这是一个很好的问题。根据《系统建模与仿真》课程内容，这涉及系统的建模与分析方法。\n\n建议你参考教材相关章节，或者将问题进一步细化（如指定具体概念、公式或仿真方法），我可以给出更精准的基于知识库的检索结果。',
	sources: [{ title: '教材目录 · 全局参考', page: '-' }]
};

// ── Mock API ──

function sleep(ms: number) {
	return new Promise((r) => setTimeout(r, ms));
}

function matchKnowledge(question: string): KnowledgeEntry {
	for (const [key, entry] of Object.entries(KNOWLEDGE)) {
		if (question.includes(key)) return entry;
	}
	return DEFAULT_KNOWLEDGE;
}

/** 获取可用模型列表 */
export async function getAgentModels(): Promise<AgentModelList> {
	await sleep(300);
	return {
		object: 'list',
		data: [
			{
				id: 'deepseek',
				name: 'deepseek',
				object: 'model',
				created: 1700000000,
				owned_by: 'tagent'
			},
			{
				id: 'mock-teaching-model',
				name: '教学大模型（Mock）',
				object: 'model',
				created: 1700000001,
				owned_by: 'tagent'
			}
		]
	};
}

/** Mock RAG 问答（对齐 POST /agent/rag/query） */
export async function queryAgentRag(
	question: string,
	model: string
): Promise<AgentRagResponse> {
	// 模拟网络延迟 1~2 秒
	await sleep(1000 + Math.random() * 1000);

	const knowledge = matchKnowledge(question);

	return {
		code: 200,
		msg: 'success',
		data: {
			user_question: question,
			final_answer: knowledge.answer,
			retrieved_context: knowledge.context,
			step_log: ['检索知识库', `匹配到 ${knowledge.sources.length} 条参考资料`, 'LLM 生成回答']
		},
		model
	};
}
