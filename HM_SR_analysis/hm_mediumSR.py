import numpy as np
import matplotlib.pyplot as plt

# ------------------------------------------------------------
# tailGauss
# ------------------------------------------------------------
def tailGauss(x, h, X, sigma, B1, B2, T):
    arg = x - X
    result = B1 + B2 * arg

    gauss = np.exp(-(arg**2) / (2.0 * sigma**2))
    tail  = np.exp(T * (2.0 * arg + T) / (2.0 * sigma**2))

    return result + np.where(x > X - T, h * gauss, h * tail)


# ------------------------------------------------------------
# modulateSR
# ------------------------------------------------------------
def modulateSR(m12, pars):
    h, X, sigma, B1, B2, T = pars

    # dense sampling to find xmax
    xscan = np.linspace(0.0, 200.0, 5000)
    Fscan = tailGauss(xscan, h, X, sigma, B1, B2, T)
    xmax = xscan[np.argmax(Fscan)]

    F10 = tailGauss(10.0, h, X, sigma, B1, B2, T)
    Fx  = tailGauss(xmax, h, X, sigma, B1, B2, T)

    Fm12 = tailGauss(m12, h, X, sigma, B1, B2, T)

    f = 1.0 - (Fm12 - F10) / (Fx - F10)
    f[m12 > xmax] = 0.0

    return f


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main():

    # Parameters
    pars = (
        3.73,    # h
        51.6,    # X
        16.6,    # sigma
       -2.62,    # B1
       -0.0266,  # B2
        6.39     # T
    )

    # m12 range
    m12_min = 10.0
    m12_max = 120.0
    m12 = np.linspace(m12_min, m12_max, 500)

    # Compute modulation
    fval = modulateSR(m12, pars)

    # Boundary: m34 = m12 * (0.85 - 0.1125 * f(m12))
    m34_boundary = m12 * (0.85 - 0.1125 * fval)

    # Upper boundary: m34 = m12
    m34_diag = m12

    # --------------------------------------------------------
    # Plot
    # --------------------------------------------------------
    plt.figure(figsize=(8, 6))

    # Shaded accepted region
    plt.fill_between(
        m12,
        m34_boundary,
        m34_diag,
        color="red",
        alpha=0.25,
        label="Accepted region"
    )

    # Boundary curve
    plt.plot(
        m12,
        m34_boundary,
        color="red",
        linewidth=2.5,
        label=r"$m_{34} = m_{12}(0.85 - 0.1125 f(m_{12}))$"
    )

    # Diagonal m34 = m12
    plt.plot(
        m12,
        m34_diag,
        linestyle="--",
        color="black",
        label=r"$m_{34} = m_{12}$"
    )

    plt.xlim(m12_min, m12_max)
    plt.ylim(0.0, m12_max)

    plt.xlabel(r"$m_{12}$ [GeV]")
    plt.ylabel(r"$m_{34}$ [GeV]")
    plt.title("Medium SR selection")

    plt.legend(frameon=False)
    plt.tight_layout()

    plt.savefig("mediumSR_boundary.pdf")
    plt.close()

    print("\nMedium SR plot saved as mediumSR_boundary.pdf")
    print("Condition:")
    print("m34 / m12 > 0.85 - 0.1125 * f(m12)")
    print("AND m34 <= m12")


if __name__ == "__main__":
    main()
