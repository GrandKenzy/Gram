// ============================================================================
// sample.c — Programa de Demostración para CExample (Gram Framework)
// ============================================================================
#include <stdio.h>

// 1. Variable global
int g_max_iterations = 100;

// 2. Prototipo de función
int add(int a, int b);

// 3. Función recursiva con condicionales if / else
int factorial(int n) {
    if (n <= 1) {
        return 1;
    } else {
        return n * factorial(n - 1);
    }
}

// 4. Función con bucle while y acumulación aritmética
int sum_to_n(int limit) {
    int total = 0;
    int i = 1;
    while (i <= limit) {
        total = total + i;
        i = i + 1;
    }
    return total;
}

// 5. Implementación del prototipo declarado
int add(int a, int b) {
    return a + b;
}

// 6. Función principal main()
int main() {
    int num = 5;
    int result_fact = factorial(num);
    int result_sum = sum_to_n(10);
    int result_add = add(result_fact, result_sum);

    if (result_add > 0) {
        return 0;
    } else {
        return 1;
    }
}
