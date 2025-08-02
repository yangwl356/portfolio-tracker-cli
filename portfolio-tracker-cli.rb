class PortfolioTrackerCli < Formula
  desc "A professional command-line tool for tracking crypto and stock investments"
  homepage "https://github.com/yangwl356/portfolio-tracker-cli"
  url "https://files.pythonhosted.org/packages/source/p/portfolio-tracker-cli/portfolio-tracker-cli-1.0.0.tar.gz"
  sha256 "c378ac6db4b3979098348570af91b3ff535a0307cefd47253b16ef2b5b2a66c8"
  license "MIT"
  head "https://github.com/yangwl356/portfolio-tracker-cli.git", branch: "main"

  depends_on "python@3.9"

  def install
    system "python3", "-m", "pip", "install", *std_pip_args, "."
  end

  test do
    system "#{bin}/portfolio", "--help"
  end
end
