import { isValidCnpj, maskCnpj } from './cnpj'

describe('cnpj', () => {
  it('validates check digits like the backend', () => {
    expect(isValidCnpj('33.000.167/0001-01')).toBe(true)
    expect(isValidCnpj('33000167000102')).toBe(false)
    expect(isValidCnpj('11111111111111')).toBe(false)
    expect(isValidCnpj('123')).toBe(false)
  })

  it('masks progressively as the user types', () => {
    expect(maskCnpj('11')).toBe('11')
    expect(maskCnpj('11222')).toBe('11.222')
    expect(maskCnpj('112223330001')).toBe('11.222.333/0001')
    expect(maskCnpj('11222333000181999')).toBe('11.222.333/0001-81')
    expect(maskCnpj('ab11.2c22')).toBe('11.222')
  })
})
