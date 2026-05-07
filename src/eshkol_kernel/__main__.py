from ipykernel.kernelapp import IPKernelApp

from .kernel import EshkolKernel


def main() -> None:
    IPKernelApp.launch_instance(kernel_class=EshkolKernel)


if __name__ == "__main__":
    main()
