! examples/bubblesort.f90 — Bubble sort with subroutine
program bubblesort
  implicit none
  integer :: arr(8), i, n

  n = 8
  arr(1) = 64
  arr(2) = 34
  arr(3) = 25
  arr(4) = 12
  arr(5) = 22
  arr(6) = 11
  arr(7) = 90
  arr(8) = 3

  print *, 'Unsorted array:'
  do i = 1, n
    print *, arr(i)
  end do

  call sort(arr, n)

  print *, 'Sorted array:'
  do i = 1, n
    print *, arr(i)
  end do

end program bubblesort

subroutine sort(arr, n)
  implicit none
  integer, intent(in) :: n
  integer, intent(inout) :: arr(n)
  integer :: i, j, temp

  do i = 1, n - 1
    do j = 1, n - i
      if (arr(j) > arr(j+1)) then
        temp = arr(j)
        arr(j) = arr(j+1)
        arr(j+1) = temp
      end if
    end do
  end do

end subroutine sort
