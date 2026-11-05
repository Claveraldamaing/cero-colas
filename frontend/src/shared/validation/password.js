export const PASSWORD_HINT = 'Entre 10 y 128 caracteres, con una mayúscula, una minúscula y un número.';
export function passwordError(value) {
  return value.length < 10 || value.length > 128 || !/[A-Z]/.test(value) || !/[a-z]/.test(value) || !/\d/.test(value) ? PASSWORD_HINT : '';
}
