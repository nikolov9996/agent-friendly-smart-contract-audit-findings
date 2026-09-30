---
id: 21191
severity: "High"
---

# Incomplete TVL Calculation in `AerodromeConnector::_getPositionTVL` Function

## Description

The [AerodromeConnector::stake](https://github.com/code-423n4/2024-04-noya/blob/9c79b332eff82011dcfa1e8fd51bad805159d758/contracts/connectors/AerodromeConnector.sol#L100) function allows to stake liquidity tokens to the gauge pool. However, the [AerodromeConnector::_getPositionTVL](https://github.com/code-423n4/2024-04-noya/blob/9c79b332eff82011dcfa1e8fd51bad805159d758/contracts/connectors/AerodromeConnector.sol#L125) function, which is responsible for calculating the Total Value Locked (TVL), does not take into account the liquidity tokens deposited in the gauge pool. This oversight will result in an incorrect calculation of the TVL, which could negatively impact the overall functionality of the protocol that utilizes the TVL metric.

## Proof of Concept

The [AerodromeConnector::stake](https://github.com/code-423n4/2024-04-noya/blob/9c79b332eff82011dcfa1e8fd51bad805159d758/contracts/connectors/AerodromeConnector.sol#L100) function allows to deposit and stake liquidity tokens in the gauge pool.

```solidity
AerodromeConnector.sol
function stake(address pool, uint256 liquidity) public onlyManager nonReentrant {
    address gauge = voter.gauges(pool);
    IERC20(pool).forceApprove(address(gauge), liquidity);
    IGauge(gauge).deposit(liquidity, address(this));  // @audit-info this sends tokens to the gauge
}
```

The implementation of the [Gauge::deposit](https://github.com/aerodrome-finance/contracts/blob/b934e7ae398ea6c251a4d5af2119776c06f1f23d/contracts/gauges/Gauge.sol#L151) is as follows:

```solidity
function deposit(uint256 _amount, address _recipient) external {
    _depositFor(_amount, _recipient);
}

function _depositFor(uint256 _amount, address _recipient) internal nonReentrant {
    if (_amount == 0) revert ZeroAmount();
    if (!IVoter(voter).isAlive(address(this))) revert NotAlive();

    address sender = _msgSender();
    _updateRewards(_recipient);

    IERC20(stakingToken).safeTransferFrom(sender, address(this), _amount); // @audit-info liquidity tokens are sent to the gauge.
    totalSupply += _amount;
    balanceOf[_recipient] += _amount;

    emit Deposit(sender, _recipient, _amount);
}
```

As evident from the preceding code snippet, when the `Gauge::deposit` function is invoked, staked liquidity tokens are sent to the gauge pool. However, the implementation of the [AerodromeConnector::_getPositionTVL](https://github.com/code-423n4/2024-04-noya/blob/9c79b332eff82011dcfa1e8fd51bad805159d758/contracts/connectors/AerodromeConnector.sol#L125) function only accounts for the liquidity tokens held in the Aerodrome pool, and does not consider the tokens that have been staked in the gauge pool. This oversight in the [AerodromeConnector::_getPositionTVL](https://github.com/code-423n4/2024-04-noya/blob/9c79b332eff82011dcfa1e8fd51bad805159d758/contracts/connectors/AerodromeConnector.sol#L125) function will result in an incomplete calculation of the Total Value Locked (TVL).

```solidity
AerodromeConnector.sol
function _getPositionTVL(HoldingPI memory p, address base) public view override returns (uint256) { 
    PositionBP memory pBP = registry.getPositionBP(vaultId, p.positionId);
    (address pool) = abi.decode(pBP.data, (address));
    uint256 balance = IERC20(pool).balanceOf(address(this)); // @audit-issue only accounts the liquidity token balance at the aerodrome pool, does not include the gauge pool
    uint256 totalSupply = IERC20(pool).totalSupply();
    (uint256 reserve0, uint256 reserve1,) = IPool(pool).getReserves();
    uint256 amount0 = balance * reserve0 / totalSupply;
    uint256 amount1 = balance * reserve1 / totalSupply;
    return _getValue(IPool(pool).token0(), base, amount0) + _getValue(IPool(pool).token1(), base, amount1);
}
```

As a result, the Total Value Locked (TVL) value calculated by the `AerodromeConnector::_getPositionTVL` function will be less than the actual value, as it does not account for the liquidity tokens staked in the gauge pool. This underestimation of the TVL could negatively impact the overall functionality of the protocol that relies on the TVL metric.

## Recommendation

It is recommended to fix the `_getPositionTVL` function to take account liquidity tokens staked in the gauge pool as follows:

```solidity
function _getPositionTVL(HoldingPI memory p, address base) public view override returns (uint256) {
    PositionBP memory pBP = registry.getPositionBP(vaultId, p.positionId);
    (address pool) = abi.decode(pBP.data, (address));
    address gauge = voter.gauges(pool);
    uint256 balance = IERC20(pool).balanceOf(address(this)) + IERC20(gauge).balanceOf(address(this));
    uint256 totalSupply = IERC20(pool).totalSupply();
    (uint256 reserve0, uint256 reserve1,) = IPool(pool).getReserves();
    uint256 amount0 = balance * reserve0 / totalSupply;
    uint256 amount1 = balance * reserve1 / totalSupply;
    return _getValue(IPool(pool).token0(), base, amount0) + _getValue(IPool(pool).token1(), base, amount1);
}
```

True, needs to be fixed.  
But I think Medium severity not High, because it’s not going to cause loss of funds in any way.

Finalizing as High Risk as TVL affects share calculation.

## Derived Narrative

The following field is derived content and may not be source-grounded:

An incomplete Total Value Locked (TVL) calculation exists in the AerodromeConnector contract. The function that reports the TVL only reads the balance of the liquidity‑token held directly in the Aerodrome pool, while the liquidity that has been deposited into the gauge contract is ignored. The root cause is that _getPositionTVL does not query the gauge’s balance of the same token, even though the stake() function transfers the tokens to the gauge via a deposit call. An attacker or a protocol that relies on the TVL metric can exploit this omission by staking liquidity, causing the reported TVL to be lower than the actual amount locked. Because many protocol components – such as share‑allocation, reward distribution, or governance weight – are derived from the TVL, the under‑reporting can lead to users receiving fewer rewards than they are entitled to, dashboards showing a smaller total value, or mis‑priced positions. The bug manifests only after liquidity has been staked in the gauge; before staking the calculation is correct. It affects any user who stakes through the connector, the protocol’s accounting logic, and any external services that consume the TVL value. The issue was discovered during a manual audit that compared the stake() implementation, which moves tokens to the gauge, with the TVL routine that only checks the pool balance. The discrepancy is subtle because the contract still holds a non‑zero balance and the gauge balance is not visible in the same storage slot, making the under‑estimation easy to miss in casual testing. The proper fix is to add the gauge’s token balance to the pool balance before converting reserves to value, i.e., balance = pool.balanceOf(this) + gauge.balanceOf(this). This brings the TVL calculation in line with the actual assets locked and restores correct reward and share calculations. The vulnerability belongs to the class of accounting or metric‑miscalculation bugs where a subset of assets is omitted from a financial aggregate.
