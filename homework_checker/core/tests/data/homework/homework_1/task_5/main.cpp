#include <iostream>

int main() {
  std::string smth, smth_else;
  std::cout << "Input string:" << std::endl;
  std::cin >> smth;
  std::cout << "Input another string:" << std::endl;
  std::cin >> smth_else;
  std::cout << smth << "_" << smth_else;
}
