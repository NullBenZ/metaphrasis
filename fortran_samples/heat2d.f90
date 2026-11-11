program heat2d
  implicit none
  integer, parameter :: nx=6, ny=5, nt=2
  integer :: i,j,n
  real :: dx=1.0, dy=1.0, dt=0.1, alpha=0.1
  real :: u(0:nx+1,0:ny+1), unew(0:nx+1,0:ny+1)
  u=0.0
  u(3,3)=1.0
  do n=1,nt
    do j=1,ny
      do i=1,nx
        unew(i,j)=u(i,j)+alpha*dt*((u(i+1,j)-2.0*u(i,j)+u(i-1,j))/(dx*dx)+(u(i,j+1)-2.0*u(i,j)+u(i,j-1))/(dy*dy))
      end do
    end do
    unew(0,:)=u(0,:)
    unew(nx+1,:)=u(nx+1,:)
    unew(:,0)=u(:,0)
    unew(:,ny+1)=u(:,ny+1)
    u=unew
  end do
  open(unit=20,file='result.txt',status='replace')
  do j=0,ny+1
    do i=0,nx+1
      write(20,'(ES24.16)') u(i,j)
    end do
  end do
  close(20)
end program heat2d
