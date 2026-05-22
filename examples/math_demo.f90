! examples/math_demo.f90 — Math functions and user-defined functions
program math_demo
  implicit none
  real :: x, pi
  integer :: n

  pi = 3.14159265358979

  print *, '=== Math Demo ==='

  ! Trigonometry
  x = pi / 4.0
  print *, 'sin(pi/4) =', sin(x)
  print *, 'cos(pi/4) =', cos(x)
  print *, 'tan(pi/4) =', tan(x)

  ! Powers and roots
  print *, 'sqrt(2)   =', sqrt(2.0)
  print *, '2**10     =', 2**10
  print *, 'exp(1)    =', exp(1.0)
  print *, 'log(e)    =', log(exp(1.0))

  ! Factorials via function
  do n = 1, 10
    print *, n, '! =', factorial(n)
  end do

end program math_demo

integer function factorial(n)
  implicit none
  integer, intent(in) :: n
  integer :: i, result

  result = 1
  do i = 2, n
    result = result * i
  end do
  factorial = result

end function factorial
