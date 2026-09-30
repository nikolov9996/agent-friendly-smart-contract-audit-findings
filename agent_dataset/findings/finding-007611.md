---
id: 7611
severity: "Critical"
---

# Missing Asset Decimal Adjustment When Calculating TVL

## Description

When the TVL is being calculated in the VaultKerosene.sol contract, the balance is multiplied with the oracle price, and adjusted with the oracle decimals.
```solidity
tvl += vault.asset().balanceOf(address(vault))
* vault.assetPrice()
/ (10**vault.oracle().decimals());
```
However, it does not adjust this based on the asset decimals. Furthermore, the assetPrice here is just a Chainlink oracle, as seen in the vault implementations.
```solidity
function assetPrice() public view returns (uint256) {
    (, int256 answer,,, uint256 updatedAt,) = oracle.latestRoundData();
    if (block.timestamp > updatedAt + STALE_DATA_TIMEOUT) revert StaleData();
    return answer.toUint256();
}
```
So if two vaults have WBTC and WETH, they will have different decimals and different amounts. But their price feeds will return the same decimals. So they will return a different scale of prices. Say both WBTC and WETH are valued at 100 USD. So price feed returns 1e10 for both. For 1e8 WBTC tvl = 1e8 * 1e10 / 1e8 = 1e10 For 1e18 WETH: tvl = 1e18 * 1e10 / 1e8 = 1e20 So WBTC is massively undervalued.

## Proof of Concept

no poc

## Recommendation

Adjust by asset decimals.
```solidity
function assetPrice() public view override returns (uint) {
    uint tvl;
    address[] memory vaults = kerosineManager.getVaults();
    uint numberOfVaults = vaults.length;
    for (uint i = 0; i < numberOfVaults; i++) {
        Vault vault = Vault(vaults[i]);
        tvl += vault.asset().balanceOf(address(vault))
        * vault.assetPrice() * 1e18
        / (10**vault.asset().decimals())
        / (10**vault.oracle().decimals());
    }
    if (tvl < dyad.totalSupply()) return 0;
    uint numerator = tvl - dyad.totalSupply();
    uint denominator = kerosineDenominator.denominator();
    return numerator * 1e8 / denominator;
}
```

## Derived Narrative

The following field is derived content and may not be source-grounded:

The vulnerability originates from the way total value locked (TVL) is calculated in the VaultKerosene.sol contract. The implementation multiplies the raw token balance by the price reported by a Chainlink oracle and then divides only by the oracle’s decimal factor. It completely omits any adjustment for the token’s own decimal precision. Because different assets such as WBTC (8 decimals) and WETH (18 decimals) share the same oracle decimal setting, the same numeric price is applied to balances that are expressed in different scales. Consequently, the TVL for a low‑decimal asset is dramatically undervalued while the TVL for a high‑decimal asset is dramatically overvalued. For example, with both assets priced at 100 USD and the oracle returning 1e10, a balance of 1e8 WBTC yields a TVL of 1e10, whereas a balance of 1e18 WETH yields a TVL of 1e20, a difference of ten orders of magnitude. This mis‑scaling can be exploited by an attacker who deposits a low‑decimal asset, causing the protocol to believe the TVL is far smaller than it actually is, which may allow the attacker to mint an excessive amount of protocol tokens, withdraw more funds than entitled, or manipulate pricing mechanisms that rely on TVL. The impact is a breach of the accounting assumptions that TVL accurately reflects the value of all assets held, leading to incorrect token issuance, distorted user dashboards, and potential loss of funds for honest participants. The bug manifests whenever the TVL aggregation loop processes vaults that hold assets with differing decimal counts, which is a common scenario in multi‑asset protocols. Users may notice that the displayed total value seems unusually low for certain assets, that their expected share of rewards is missing, or that token prices appear inconsistent with market rates. The issue was uncovered during a manual security audit that compared the arithmetic of the TVL function against the known decimal specifications of the assets. It is hard to spot because the contract compiles and runs without reverting, and the TVL numbers may still be non‑zero, giving a false sense of correctness. The proper remediation is to incorporate the asset’s decimal factor into the calculation, typically by multiplying the intermediate result by a common scaling constant (e.g., 1e18) and then dividing by both the asset’s decimals and the oracle’s decimals. This ensures that all assets are normalized to the same base unit before aggregation, restoring accurate accounting and preventing the described exploitation scenario.
