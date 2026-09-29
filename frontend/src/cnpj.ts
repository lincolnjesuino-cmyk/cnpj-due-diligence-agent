// Same check-digit algorithm as backend/app/cnpj.py, for instant feedback in the form.

const W1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
const W2 = [6, ...W1]

function checkDigit(digits: number[], weights: number[]): number {
  const sum = digits.reduce((acc, d, i) => acc + d * (weights[i] ?? 0), 0)
  const remainder = sum % 11
  return remainder < 2 ? 0 : 11 - remainder
}

export function onlyDigits(value: string): string {
  return value.replace(/\D/g, '')
}

export function isValidCnpj(value: string): boolean {
  const d = onlyDigits(value)
  if (d.length !== 14 || /^(\d)\1{13}$/.test(d)) return false
  const n = [...d].map(Number)
  return checkDigit(n.slice(0, 12), W1) === n[12] && checkDigit(n.slice(0, 13), W2) === n[13]
}

/** Progressive mask: 11222333000181 -> 11.222.333/0001-81 */
export function maskCnpj(value: string): string {
  const d = onlyDigits(value).slice(0, 14)
  const parts = [d.slice(0, 2), d.slice(2, 5), d.slice(5, 8), d.slice(8, 12), d.slice(12, 14)]
  let out = parts[0] ?? ''
  if (d.length > 2) out += `.${parts[1]}`
  if (d.length > 5) out += `.${parts[2]}`
  if (d.length > 8) out += `/${parts[3]}`
  if (d.length > 12) out += `-${parts[4]}`
  return out
}
