! examples/fibonacci.f90 — Fibonacci sequence
program fibonacci
  implicit none
  integer :: n, i, a, b, temp

  n = 15
  a = 0
  b = 1

  print *, 'Fibonacci sequence (first', n, 'terms):'
  print *, a, b

  do i = 3, n
    temp = a + b
    a = b
    b = temp
    print *, b
  end do

end program fibonacci
