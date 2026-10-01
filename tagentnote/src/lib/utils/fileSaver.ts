/**
 * A lightweight wrapper around the FileSaver fallback approach.
 * Saves a string as a file download in the browser.
 */
function saveAs(content: string | Blob, filename: string, mime = 'application/octet-stream') {
	if (typeof window === 'undefined') return;
	const blob =
		typeof content === 'string'
			? new Blob([content], { type: mime || 'text/plain;charset=utf-8' })
			: content;
	const url = URL.createObjectURL(blob);
	const link = document.createElement('a');
	link.href = url;
	link.download = filename;
	document.body.appendChild(link);
	link.click();
	document.body.removeChild(link);
	setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const fileSaver = { saveAs };
