export interface TextSelection { start: number; end: number }
export interface TextEdit extends TextSelection { text: string; changed: boolean }
export function normalizeSelection(text: string, start: number, end: number): TextSelection | null
export function highlightSelection(text: string, start: number, end: number): TextEdit
export function unhighlightSelection(text: string, start: number, end: number): TextEdit
export function escapeTableCell(value: string): string
export function buildMarkdownTable(headers: string[], rows: string[][]): string
export function insertTableAtSelection(text: string, start: number, end: number, table: string): TextEdit
